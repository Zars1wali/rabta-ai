const express = require('express');
const cors = require('cors');
const qrcode = require('qrcode');
const axios = require('axios');
const path = require('path');
const fs = require('fs');
const { default: makeWASocket, useMultiFileAuthState, DisconnectReason, downloadMediaMessage } = require('@whiskeysockets/baileys');
const pino = require('pino');

const app = express();
app.use(cors());
app.use(express.json({ limit: '25mb' }));

const PORT = 3001;
const PYTHON_BACKEND_URL = process.env.PYTHON_BACKEND_URL || 'http://localhost:8000';
const APPROVED_FILE = path.join(__dirname, 'approved_numbers.json');
const AUTH_DIR = path.join(__dirname, 'auth_session');

function cleanPhoneNumber(phone) {
    if (!phone) return '';
    let digits = String(phone).replace(/\D/g, '');
    if (digits.startsWith('03')) {
        digits = '92' + digits.slice(1);
    } else if (digits.startsWith('0092')) {
        digits = digits.slice(2);
    }
    return digits;
}

function getApprovedNumbers() {
    try {
        if (fs.existsSync(APPROVED_FILE)) {
            const raw = fs.readFileSync(APPROVED_FILE, 'utf8');
            return JSON.parse(raw).approved_numbers || [];
        }
    } catch(e) {}
    return [];
}

let sock = null;
let currentQR = null;
let connectionStatus = 'DISCONNECTED'; // DISCONNECTED, SCANNING, CONNECTED
let connectedNumber = null;
const processedMsgIds = new Set(); // Dedup guard: Baileys re-delivers messages after reconnects

function extractTextMessage(message) {
    if (!message) return '';
    // Unwrap common envelopes (disappearing messages, view-once, ephemeral)
    let m = message;
    for (let i = 0; i < 5; i++) {
        if (m.ephemeralMessage) { m = m.ephemeralMessage.message; continue; }
        if (m.viewOnceMessage) { m = m.viewOnceMessage.message; continue; }
        if (m.viewOnceMessageV2) { m = m.viewOnceMessageV2.message; continue; }
        if (m.documentWithCaptionMessage) { m = m.documentWithCaptionMessage.message; continue; }
        break;
    }
    return m.conversation ||
           m.extendedTextMessage?.text ||
           m.imageMessage?.caption ||
           m.videoMessage?.caption ||
           m.documentMessage?.caption ||
           m.buttonsResponseMessage?.selectedButtonId ||
           m.listResponseMessage?.singleSelectReply?.selectedRowId ||
           '';
}

async function connectToWhatsApp(forceClean = false) {
    if (forceClean && fs.existsSync(AUTH_DIR)) {
        console.log('🧹 Clearing auth session...');
        try {
            fs.rmSync(AUTH_DIR, { recursive: true, force: true });
        } catch(e) {}
    }

    const { state, saveCreds } = await useMultiFileAuthState(AUTH_DIR);

    sock = makeWASocket({
        auth: state,
        logger: pino({ level: 'silent' }),
        connectTimeoutMs: 60000,
        defaultQueryTimeoutMs: 60000,
    });

    sock.ev.on('creds.update', saveCreds);

    sock.ev.on('connection.update', async (update) => {
        const { connection, lastDisconnect, qr } = update;

        if (qr) {
            currentQR = await qrcode.toDataURL(qr);
            connectionStatus = 'SCANNING';
            console.log('📱 Fresh WhatsApp QR Code generated! Open http://localhost:3001');
        }

        if (connection === 'close') {
            try {
                const statusCode = (lastDisconnect?.error)?.output?.statusCode;
                console.log(`Connection closed (code ${statusCode}).`);

                connectionStatus = 'DISCONNECTED';
                currentQR = null;

                if (statusCode === DisconnectReason.loggedOut || statusCode === 401) {
                    console.log('Session logged out or expired. Resetting session...');
                    setTimeout(() => connectToWhatsApp(true), 2000);
                } else if (statusCode === DisconnectReason.connectionReplaced || statusCode === 440) {
                    // Another linked device took over this session.
                    // Do NOT reconnect instantly — it starts a takeover war with the other device.
                    console.warn('⚠️ CONFLICT (440): This WhatsApp session was taken over by ANOTHER device/server!');
                    console.warn('⚠️ If the bot is supposed to run HERE, log out the other device on your phone:');
                    console.warn('⚠️   WhatsApp > Settings > Linked Devices > select the old session > Log Out');
                    console.warn('⚠️ Retrying in 60 seconds...');
                    setTimeout(() => connectToWhatsApp(false), 60000);
                } else {
                    const delay = Math.min(2000 + Math.floor(Math.random() * 3000), 15000);
                    console.log(`Reconnecting in ${delay}ms...`);
                    setTimeout(() => connectToWhatsApp(false), delay);
                }
            } catch (err) {
                console.error('Error in close handler:', err.message);
                setTimeout(() => connectToWhatsApp(false), 5000);
            }
        } else if (connection === 'open') {
            try {
                if (!sock.user || !sock.user.id) {
                    console.error('Connection opened but user info missing. Skipping authorization check.');
                    return;
                }
                connectedNumber = cleanPhoneNumber(sock.user.id.split(':')[0]);
                console.log(`\n🔍 Checking authorization for phone: +${connectedNumber}...`);

                // Security Whitelist Verification with normalized phone numbers
                const approvedList = getApprovedNumbers();
                const isApproved = approvedList.some(item => {
                    const normItem = cleanPhoneNumber(item.phone);
                    return normItem === connectedNumber && item.status === 'APPROVED';
                });

                if (!isApproved) {
                    console.warn(`\n🚫 ACCESS DENIED: +${connectedNumber} is NOT on the approved Rabta AI whitelist.`);
                    connectionStatus = 'UNAUTHORIZED';
                    currentQR = null;
                    try {
                        await sock.logout();
                    } catch(e) {}
                    return;
                }

                console.log(`✅ ACCESS GRANTED: +${connectedNumber} is verified and authorized on Rabta AI!`);
                connectionStatus = 'CONNECTED';
                currentQR = null;
            } catch (err) {
                console.error('Error during connection open handling:', err.message);
            }
        }
    });

    // Listen for incoming WhatsApp messages
    sock.ev.on('messages.upsert', async (m) => {
        if (m.type !== 'notify') return; // Ignore history sync / app state dumps

        for (const msg of m.messages) {
            if (!msg || !msg.message) continue;
            if (msg.key.fromMe) continue; // Don't reply to own outgoing messages

            const msgId = msg.key.id;
            if (!msgId || processedMsgIds.has(msgId)) continue; // Skip duplicates
            processedMsgIds.add(msgId);
            if (processedMsgIds.size > 5000) {
                const oldest = processedMsgIds.values().next().value;
                processedMsgIds.delete(oldest);
            }

            const sender = msg.key.remoteJid;
            if (!sender || sender.includes('@g.us')) continue; // Ignore groups
            if (sender.includes('@broadcast') || sender.includes('@newsletter')) continue; // Ignore status/newsletters
            if (connectedNumber && sender.split('@')[0] === connectedNumber) continue; // Ignore self-chat

            const senderPhone = sender.split('@')[0];

            // Extract text message (handles ephemeral / view-once wrappers)
            const textMessage = extractTextMessage(msg.message);

            // Extract image if attached or quoted
            let imageBase64 = null;
            let m = msg.message;
            if (m.ephemeralMessage) m = m.ephemeralMessage.message;
            if (m.viewOnceMessage) m = m.viewOnceMessage.message;
            if (m.viewOnceMessageV2) m = m.viewOnceMessageV2.message;

            const isImage = !!m.imageMessage;
            const isQuotedImage = !!m.extendedTextMessage?.contextInfo?.quotedMessage?.imageMessage;

            if (isImage) {
                try {
                    const buffer = await downloadMediaMessage(msg, 'buffer', {});
                    if (buffer && buffer.length > 0) {
                        imageBase64 = buffer.toString('base64');
                        console.log(`📸 Downloaded customer image (${Math.round(buffer.length / 1024)} KB)`);
                    }
                } catch (e) {
                    console.warn(`[${senderPhone}] Could not download image:`, e.message);
                }
            } else if (isQuotedImage) {
                try {
                    const quotedMsg = {
                        key: { remoteJid: sender },
                        message: m.extendedTextMessage.contextInfo.quotedMessage
                    };
                    const buffer = await downloadMediaMessage(quotedMsg, 'buffer', {});
                    if (buffer && buffer.length > 0) {
                        imageBase64 = buffer.toString('base64');
                        console.log(`📸 Downloaded quoted image (${Math.round(buffer.length / 1024)} KB)`);
                    }
                } catch (e) {
                    console.warn(`[${senderPhone}] Could not download quoted image:`, e.message);
                }
            }

            const promptText = textMessage || (imageBase64 ? 'Ye photo mein konsi product hai aur iski price kya hai?' : '');
            if (!promptText && !imageBase64) continue;

            console.log(`📩 Incoming WhatsApp from [${senderPhone}]: "${promptText}" ${imageBase64 ? '[WITH IMAGE]' : ''}`);

            try {
                // Forward to Python Gemini AI Brain with image support
                const response = await axios.post(`${PYTHON_BACKEND_URL}/api/gateway/process-message`, {
                    customer_phone: senderPhone,
                    business_phone: connectedNumber || 'default',
                    message: promptText,
                    image_base64: imageBase64,
                    platform: 'baileys_qr'
                }, { timeout: 60000 });

                const replyChunks = response.data?.reply_chunks;
                const replyText = response.data?.reply;

                if (replyChunks && replyChunks.length > 0) {
                    // Send each chunk as a separate short WhatsApp message
                    // with a natural typing delay between them
                    for (let i = 0; i < replyChunks.length; i++) {
                        if (i > 0) await new Promise(r => setTimeout(r, 1200)); // natural pause
                        console.log(`🤖 [${i+1}/${replyChunks.length}] Replying to [${senderPhone}]: "${replyChunks[i].substring(0, 80)}..."`);
                        await sock.sendMessage(sender, { text: replyChunks[i] });
                    }
                } else if (replyText) {
                    console.log(`🤖 Replying to [${senderPhone}]: "${replyText.substring(0, 100)}..."`);
                    await sock.sendMessage(sender, { text: replyText });
                }
            } catch (error) {
                console.error(`[${senderPhone}] Backend error: ${error.message}`);

                // CRITICAL: Always send a fallback reply — never leave customer in silence
                try {
                    const fallback = "Maaf kijiye, abhi technical issue hai. Thori der mein dobara try karein ya hum aap se rabta karenge.";
                    await sock.sendMessage(sender, { text: fallback });
                    console.log(`⚠️ Fallback reply sent to [${senderPhone}]`);
                } catch (sendErr) {
                    console.error(`[${senderPhone}] Failed to send fallback: ${sendErr.message}`);
                }

                processedMsgIds.delete(msgId); // Allow retry on next delivery
            }
        }
    });
}

// Reset endpoint to generate new QR on demand
app.post('/reset', async (req, res) => {
    console.log('🔄 Manual QR reset requested.');
    currentQR = null;
    connectionStatus = 'DISCONNECTED';
    if (sock) {
        try { sock.end(); } catch(e) {}
    }
    connectToWhatsApp(true);
    res.json({ status: 'RESETTING', message: 'Generating fresh QR code...' });
});

// API endpoint to get the live QR code
app.get('/qr', (req, res) => {
    res.json({
        status: connectionStatus,
        qr: currentQR,
        connected_number: connectedNumber
    });
});

// Web UI to display the QR code with Live Polling & Force Refresh Button
app.get('/', (req, res) => {
    res.send(`
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>Connect WhatsApp — Rabta AI</title>
        <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;600;700;800&display=swap" rel="stylesheet">
        <style>
            * { margin:0; padding:0; box-sizing:border-box; font-family:'Plus Jakarta Sans',sans-serif; }
            body { background:#070B14; color:#F3F4F6; display:flex; justify-content:center; align-items:center; min-height:100vh; padding:20px; }
            .card { background:#0F172A; border:1px solid #1E293B; border-radius:24px; padding:40px; max-width:480px; width:100%; text-align:center; box-shadow:0 30px 70px rgba(0,0,0,0.6); }
            .logo { font-size:26px; font-weight:800; color:#10B981; margin-bottom:8px; }
            .subtitle { color:#94A3B8; font-size:14px; margin-bottom:24px; line-height:1.5; }
            .qr-box { background:#FFFFFF; padding:16px; border-radius:18px; width:260px; height:260px; margin:0 auto 20px auto; display:flex; justify-content:center; align-items:center; box-shadow: 0 10px 30px rgba(0,0,0,0.4); }
            .qr-box img { width:100%; height:100%; border-radius:10px; }
            .status-badge { display:inline-block; padding:6px 16px; border-radius:9999px; font-size:13px; font-weight:700; margin-bottom:16px; }
            .status-SCANNING { background:rgba(245, 158, 11, 0.15); color:#FBBF24; border:1px solid rgba(245, 158, 11, 0.3); }
            .status-CONNECTED { background:rgba(16, 185, 129, 0.15); color:#34D399; border:1px solid rgba(16, 185, 129, 0.3); }
            .status-DISCONNECTED { background:rgba(239, 68, 68, 0.15); color:#F87171; border:1px solid rgba(239, 68, 68, 0.3); }
            .btn-refresh { background:#1E293B; color:#E2E8F0; border:1px solid #334155; padding:10px 20px; border-radius:12px; font-weight:600; font-size:13px; cursor:pointer; margin-top:14px; transition:all 0.2s; }
            .btn-refresh:hover { background:#334155; color:#FFF; }
            .instructions { text-align:left; background:#0B0F19; border:1px solid #1E293B; border-radius:14px; padding:16px; font-size:13px; color:#CBD5E1; margin-top:20px; }
            .instructions ol { padding-left:20px; line-height:1.8; }
        </style>
    </head>
    <body>
        <div class="card">
            <div class="logo">RABTA AI ⚡</div>
            <div class="subtitle">Scan this QR code with WhatsApp on your phone to connect in 10 seconds.</div>
            
            <div id="statusBadge" class="status-badge status-SCANNING">Generating QR Code...</div>

            <div class="qr-box" id="qrContainer">
                <p style="color:#64748B; font-size:13px; font-weight:600;">Loading QR Code...</p>
            </div>

            <button class="btn-refresh" onclick="forceResetQR()">🔄 Generate Fresh QR Code</button>

            <div class="instructions">
                <strong>How to connect:</strong>
                <ol>
                    <li>Open <strong>WhatsApp</strong> on your phone</li>
                    <li>Tap <strong>Settings</strong> or <strong>Three Dots (⋮)</strong></li>
                    <li>Tap <strong>Linked Devices</strong> &gt; <strong>Link a Device</strong></li>
                    <li>Scan this QR code with your camera</li>
                </ol>
            </div>
        </div>

        <script>
            async function checkStatus() {
                try {
                    const res = await fetch('/qr');
                    const data = await res.json();
                    
                    const badge = document.getElementById('statusBadge');
                    const container = document.getElementById('qrContainer');
                    
                    badge.className = 'status-badge status-' + data.status;
                    
                    if (data.status === 'CONNECTED') {
                        badge.innerText = 'Connected: +' + data.connected_number;
                        container.innerHTML = '<div style="text-align:center;"><p style="font-size:44px;">✅</p><p style="color:#10B981; font-weight:700; font-size:16px; margin-top:8px;">WhatsApp Connected!</p><p style="color:#64748B; font-size:12px; margin-top:4px;">AI is now replying to incoming chats.</p></div>';
                    } else if (data.qr) {
                        badge.innerText = 'Scan QR Code Now';
                        container.innerHTML = '<img src="' + data.qr + '" alt="WhatsApp QR Code">';
                    }
                } catch(e) {}
            }

            async function forceResetQR() {
                document.getElementById('statusBadge').innerText = 'Resetting & Generating Fresh QR...';
                document.getElementById('qrContainer').innerHTML = '<p style="color:#64748B; font-size:13px;">Generating...</p>';
                await fetch('/reset', { method: 'POST' });
                setTimeout(checkStatus, 1500);
            }

            setInterval(checkStatus, 2000);
            checkStatus();
        </script>
    </body>
    </html>
    `);
});

// Never let an async error kill the whole gateway process
process.on('uncaughtException', (err) => {
    console.error('Uncaught exception (gateway kept alive):', err.message);
});
process.on('unhandledRejection', (err) => {
    console.error('Unhandled rejection (gateway kept alive):', err);
});

// Health check endpoint — used by Docker HEALTHCHECK and UptimeRobot
app.get('/health', (req, res) => {
    res.json({
        status: 'ok',
        whatsapp: connectionStatus,
        connected_number: connectedNumber || null,
        uptime_seconds: Math.floor(process.uptime()),
    });
});

// Start gateway — reuse saved session if it exists (forceClean only via /reset)
connectToWhatsApp(false);

app.listen(PORT, () => {
    console.log(`🚀 WhatsApp QR Gateway running at http://localhost:${PORT}`);
});
