const {
    default: makeWASocket,
    useMultiFileAuthState,
    DisconnectReason,
    fetchLatestBaileysVersion,
    makeInMemoryStore,
    makeCacheableSignalKeyStore,
    downloadMediaMessage
} = require('@whiskeysockets/baileys');
const express = require('express');
const axios = require('axios');
const QRCode = require('qrcode');
const pino = require('pino');
const fs = require('fs');
const path = require('path');

const app = express();
app.use(express.json({ limit: '50mb' }));
app.use(express.urlencoded({ extended: true, limit: '50mb' }));

const PORT = process.env.PORT || 3001;
const PYTHON_BACKEND_URL = process.env.PYTHON_BACKEND_URL || 'http://localhost:8000';
const AUTH_DIR = path.join(__dirname, 'auth_session');

const sentMsgCache = new Map();

let sock = null;
let qrCodeData = null;
let connectionStatus = 'DISCONNECTED';
let pairingCode = null;
let connectedNumber = null;
const processedMsgIds = new Set();

function cleanPhoneNumber(phone) {
    if (!phone) return '';
    let digits = phone.replace(/\D/g, '');
    if (digits.startsWith('0') && digits.length === 11) {
        digits = '92' + digits.substring(1);
    }
    return digits;
}

function extractTextMessage(message) {
    if (!message) return '';
    if (message.conversation) return message.conversation;
    if (message.extendedTextMessage?.text) return message.extendedTextMessage.text;
    if (message.imageMessage?.caption) return message.imageMessage.caption;
    if (message.videoMessage?.caption) return message.videoMessage.caption;
    if (message.ephemeralMessage?.message) return extractTextMessage(message.ephemeralMessage.message);
    if (message.viewOnceMessage?.message) return extractTextMessage(message.viewOnceMessage.message);
    if (message.viewOnceMessageV2?.message) return extractTextMessage(message.viewOnceMessageV2.message);
    return '';
}

// Per-customer async queue
const customerQueues = new Map();

// Outgoing message deduplication cache (prevents duplicate messages to the same JID within 30 seconds)
const recentOutgoingCache = new Map();
function isDuplicateOutgoing(jid, text) {
    if (!text || !jid) return false;
    const cleanText = text.trim();
    const key = `${jid}:${cleanText}`;
    const now = Date.now();
    const lastSent = recentOutgoingCache.get(key);
    if (lastSent && (now - lastSent) < 30000) {
        return true;
    }
    recentOutgoingCache.set(key, now);
    if (recentOutgoingCache.size > 500) {
        for (const [k, ts] of recentOutgoingCache.entries()) {
            if (now - ts > 60000) recentOutgoingCache.delete(k);
        }
    }
    return false;
}

function enqueueCustomerMessage(phone, taskFn) {
    const prev = customerQueues.get(phone) || Promise.resolve();
    const next = prev.then(taskFn).catch(err => {
        console.error(`[${phone}] Queue task error:`, err.message);
    });
    customerQueues.set(phone, next);
    next.finally(() => {
        if (customerQueues.get(phone) === next) {
            customerQueues.delete(phone);
        }
    });
}

async function handleIncomingMessage(msg) {
    const sender = msg.key.remoteJid;
    if (!sender || sender.includes('@g.us')) return;
    if (sender.includes('@broadcast') || sender.includes('@newsletter')) return;
    if (connectedNumber && sender.split('@')[0] === connectedNumber) return;

    const senderPhone = sender.split('@')[0];
    const msgId = msg.key.id;

    const textMessage = extractTextMessage(msg.message);

    let imageBase64 = null;
    let audioBase64 = null;
    let audioMime = null;
    let m = msg.message;
    if (m.ephemeralMessage) m = m.ephemeralMessage.message;
    if (m.viewOnceMessage) m = m.viewOnceMessage.message;
    if (m.viewOnceMessageV2) m = m.viewOnceMessageV2.message;

    const isImage = !!m.imageMessage;
    const isQuotedImage = !!m.extendedTextMessage?.contextInfo?.quotedMessage?.imageMessage;
    const isAudio = !!m.audioMessage;

    if (isAudio) {
        try {
            const buffer = await downloadMediaMessage(msg, 'buffer', {});
            if (buffer && buffer.length > 0) {
                audioBase64 = buffer.toString('base64');
                audioMime = m.audioMessage?.mimetype || 'audio/ogg; codecs=opus';
                console.log(`🎙️ Downloaded voice note (${Math.round(buffer.length / 1024)} KB)`);
            }
        } catch (e) {
            console.warn(`[${senderPhone}] Could not download audio:`, e.message);
        }
    } else if (isImage) {
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

    // Strict Single-Owner Enforcement: Only 1 active owner exists at any time
    const OWNER_PHONE = process.env.OWNER_PHONE || '+923169827188';
    const OWNER_LID = process.env.OWNER_LID || '61379545444551';
    const OWNER_MATCHERS = [
        OWNER_PHONE.replace(/[^\d]/g, '').slice(-10), // e.g. '3169827188'
        OWNER_LID.replace(/[^\d]/g, ''),               // e.g. '61379545444551'
    ].filter(Boolean);

    // Ensure stale/previous owner JID is never used
    if (global._lastKnownOwnerJid && !OWNER_MATCHERS.some(m => global._lastKnownOwnerJid.includes(m))) {
        global._lastKnownOwnerJid = `${OWNER_LID}@lid`;
    }
    if (!global._lastKnownOwnerJid) {
        global._lastKnownOwnerJid = `${OWNER_LID}@lid`;
    }

    const isOwnerMsg = OWNER_MATCHERS.some(matcher => senderPhone.includes(matcher) || sender.includes(matcher));
    if (isOwnerMsg) {
        global._lastKnownOwnerJid = sender;
        console.log(`👑 [BOSS] Recognized Active Owner: ${sender}`);
    } else {
        console.log(`👤 [CUSTOMER] Inbound message from: ${senderPhone}`);
    }
    const effectiveSenderPhone = isOwnerMsg ? OWNER_PHONE : senderPhone;

    // Detect Real SIM Phone Number (especially when privacy LID is used)
    const isLid = sender.endsWith('@lid');
    let realSimPhone = null;
    if (!isLid && sender.endsWith('@s.whatsapp.net')) {
        realSimPhone = sender.split('@')[0];
    } else {
        const p = msg.key?.participant || msg.participant || m?.extendedTextMessage?.contextInfo?.participant;
        if (p && p.endsWith('@s.whatsapp.net')) {
            realSimPhone = p.split('@')[0];
        }
    }
    const pushName = msg.pushName || null;

    // Track customer JID so relay back to customer always uses correct destination
    if (!isOwnerMsg) {
        if (!global._customerJidMap) global._customerJidMap = new Map();
        global._customerJidMap.set(senderPhone, sender);
        if (realSimPhone) global._customerJidMap.set(realSimPhone, sender);
    }

    const promptText = textMessage
        || (imageBase64 ? (isOwnerMsg ? 'Add new product from photo' : 'Ye photo mein konsi product hai aur iski price kya hai?') : '')
        || (audioBase64 ? '[VOICE NOTE — transcribe and respond]' : '');
    if (!promptText && !imageBase64 && !audioBase64) return;

    console.log(`📩 Incoming WhatsApp from [${effectiveSenderPhone}] (SIM: ${realSimPhone || 'unknown'}, Name: ${pushName}): "${promptText.substring(0, 60)}"`);

    try {
        const response = await axios.post(`${PYTHON_BACKEND_URL}/api/gateway/process-message`, {
            customer_phone: effectiveSenderPhone,
            real_phone: realSimPhone,
            push_name: pushName,
            sender_jid: sender,
            business_phone: connectedNumber || 'default',
            message: promptText,
            image_base64: imageBase64,
            audio_base64: audioBase64,
            audio_mime: audioMime,
            platform: 'baileys_qr'
        }, { timeout: 120000 });

        const replyText = response.data?.reply;
        const replyChunks = response.data?.reply_chunks;
        const mediaUrl = response.data?.media_url;
        const ownerAlert = response.data?.owner_alert;
        const ownerPhone = response.data?.owner_phone;
        const forwardCustomer = response.data?.forward_to_customer;
        const forwardMessage = response.data?.forward_message;


        // 1. Natural human typing delay for customer messages (2.5 - 3.8s)
        if (!isOwnerMsg) {
            const delay = Math.floor(Math.random() * 1300) + 2500;
            await new Promise(r => setTimeout(r, delay));
        }

        // 2. Send image(s) or text reply to the sender
        const rawMediaUrls = response.data?.media_urls;
        let mediaUrls = [];
        if (Array.isArray(rawMediaUrls) && rawMediaUrls.length > 0) {
            mediaUrls = rawMediaUrls.map((u, idx) => {
                const urlStr = typeof u === 'string' ? u : (u ? u.url : null);
                const captionStr = typeof u === 'string' ? (idx === 0 ? (replyText || undefined) : undefined) : (u ? u.caption : undefined);
                return { url: urlStr, caption: captionStr };
            }).filter(item => item && item.url);
        } else if (mediaUrl) {
            const urlStr = typeof mediaUrl === 'string' ? mediaUrl : mediaUrl?.url;
            if (urlStr) {
                mediaUrls = [{ url: urlStr, caption: replyText || undefined }];
            }
        }

        if (mediaUrls.length > 0) {
            for (let i = 0; i < mediaUrls.length; i++) {
                if (i > 0) await new Promise(r => setTimeout(r, 1500));
                const item = mediaUrls[i];
                console.log(`📸 Sending product image ${i + 1}/${mediaUrls.length} to [${senderPhone}]: ${item.url}`);
                try {
                    const sent = await sock.sendMessage(sender, {
                        image: { url: item.url },
                        caption: item.caption || undefined
                    });
                    if (sent?.key?.id) sentMsgCache.set(sent.key.id, sent.message);
                } catch (mediaErr) {
                    console.error(`Failed to send image ${item.url}, falling back to text: ${mediaErr.message}`);
                    if (item.caption) {
                        const sent = await sock.sendMessage(sender, { text: item.caption });
                        if (sent?.key?.id) sentMsgCache.set(sent.key.id, sent.message);
                    }
                }
            }
        } else if (replyChunks && replyChunks.length > 0) {
            for (let i = 0; i < replyChunks.length; i++) {
                if (i > 0) await new Promise(r => setTimeout(r, 1200));
                console.log(`🤖 Replying to [${senderPhone}]: "${replyChunks[i].substring(0, 80)}..."`);
                const sent = await sock.sendMessage(sender, { text: replyChunks[i] });
                if (sent?.key?.id) sentMsgCache.set(sent.key.id, sent.message);
            }
        } else if (replyText) {
            console.log(`🤖 Replying to [${senderPhone}]: "${replyText.substring(0, 100)}..."`);
            const sent = await sock.sendMessage(sender, { text: replyText });
            if (sent?.key?.id) sentMsgCache.set(sent.key.id, sent.message);
        }

        // 3. Relay owner answer to customer if owner answered
        if (forwardCustomer && forwardMessage) {
            const custJid = (global._customerJidMap && global._customerJidMap.get(forwardCustomer))
                || (global._customerJidMap && global._customerJidMap.get(cleanPhoneNumber(forwardCustomer)))
                || `${cleanPhoneNumber(forwardCustomer)}@s.whatsapp.net`;
            if (isDuplicateOutgoing(custJid, forwardMessage)) {
                console.log(`🛡️ [DEDUP] Suppressed duplicate relay to customer [${forwardCustomer}]`);
            } else {
                console.log(`📨 [RELAY] Forwarding Boss decision to customer [${forwardCustomer}] (JID: ${custJid}): "${forwardMessage.substring(0, 80)}..."`);
                await new Promise(r => setTimeout(r, 1500));
                const sent = await sock.sendMessage(custJid, { text: forwardMessage });
                if (sent?.key?.id) sentMsgCache.set(sent.key.id, sent.message);
            }
        }

        // 4. Send clean notification to the Boss
        if (ownerAlert && ownerPhone) {
            const targetOwnerJid = global._lastKnownOwnerJid || `${cleanPhoneNumber(ownerPhone)}@s.whatsapp.net`;
            if (isDuplicateOutgoing(targetOwnerJid, ownerAlert)) {
                console.log(`🛡️ [DEDUP] Suppressed duplicate alert to Boss on [${targetOwnerJid}]`);
            } else {
                console.log(`🚨 [ALERT] Notifying Boss on [${targetOwnerJid}]`);
                const sent = await sock.sendMessage(targetOwnerJid, { text: ownerAlert });
                if (sent?.key?.id) sentMsgCache.set(sent.key.id, sent.message);
            }
        }
    } catch (error) {
        console.error(`[${senderPhone}] Gateway bridge error: ${error.message}`);
        try {
            const fallback = "Walaikum Assalam! Jee bhai, Haider Arms mein khushamdeed. Batayein kis firearm ya product ke baare mein maloomat chahiye?";
            await sock.sendMessage(sender, { text: fallback });
        } catch (sendErr) {
            console.error(`[${senderPhone}] Fallback send failed: ${sendErr.message}`);
        }
        processedMsgIds.delete(msgId);
    }
}

async function connectToWhatsApp() {
    const { state, saveCreds } = await useMultiFileAuthState(AUTH_DIR);
    const { version, isLatest } = await fetchLatestBaileysVersion();
    console.log(`Using Baileys version ${version.join('.')}, isLatest: ${isLatest}`);

    sock = makeWASocket({
        version,
        logger: pino({ level: 'silent' }),
        printQRInTerminal: false,
        auth: {
            creds: state.creds,
            keys: makeCacheableSignalKeyStore(state.keys, pino({ level: 'silent' }))
        },
        browser: ['Rabta AI', 'Chrome', '120.0.0'],
        syncFullHistory: false,
        markOnlineOnConnect: true,
        connectTimeoutMs: 60000,
        keepAliveIntervalMs: 25000,
        getMessage: async (key) => {
            if (sentMsgCache.has(key.id)) {
                return sentMsgCache.get(key.id);
            }
            return undefined;
        }
    });

    sock.ev.on('creds.update', saveCreds);

    sock.ev.on('connection.update', async (update) => {
        const { connection, lastDisconnect, qr } = update;

        if (qr) {
            qrCodeData = qr;
            connectionStatus = 'WAITING_FOR_QR_SCAN';
            console.log('\nScan QR Code on WhatsApp:');
            QRCode.toString(qr, { type: 'terminal', small: true }).then(console.log).catch(() => {});
        }

        if (connection === 'close') {
            const statusCode = lastDisconnect?.error?.output?.statusCode;
            const shouldReconnect = statusCode !== DisconnectReason.loggedOut;
            console.log(`Connection closed (status: ${statusCode}). Reconnecting: ${shouldReconnect}`);
            connectionStatus = 'DISCONNECTED';
            qrCodeData = null;
            pairingCode = null;

            if (shouldReconnect) {
                setTimeout(connectToWhatsApp, 5000);
            } else {
                console.log('Logged out. Clearing auth directory...');
                try {
                    fs.rmSync(AUTH_DIR, { recursive: true, force: true });
                } catch (e) {}
                setTimeout(connectToWhatsApp, 3000);
            }
        } else if (connection === 'open') {
            connectionStatus = 'CONNECTED';
            qrCodeData = null;
            pairingCode = null;
            connectedNumber = sock.user?.id?.split(':')[0] || sock.user?.id?.split('@')[0];
            console.log(`\n========================================`);
            console.log(`  WhatsApp Connected Successfully!`);
            console.log(`  Phone Number: ${connectedNumber}`);
            console.log(`========================================\n`);
        }
    });

    sock.ev.on('messages.upsert', async (m) => {
        if (m.type !== 'notify') return;

        for (const msg of m.messages) {
            if (!msg || !msg.message) continue;
            if (msg.key.fromMe) continue;

            const msgId = msg.key.id;
            if (!msgId || processedMsgIds.has(msgId)) continue;
            processedMsgIds.add(msgId);
            if (processedMsgIds.size > 5000) {
                const oldest = processedMsgIds.values().next().value;
                processedMsgIds.delete(oldest);
            }

            const sender = msg.key.remoteJid;
            if (!sender || sender.includes('@g.us')) continue;
            const senderPhone = sender.split('@')[0];

            enqueueCustomerMessage(senderPhone, () => handleIncomingMessage(msg));
        }
    });
}

// Express Endpoints
app.get('/health', (req, res) => {
    res.json({
        status: connectionStatus === 'CONNECTED' ? 'healthy' : 'disconnected',
        whatsapp_status: connectionStatus,
        connected_number: connectedNumber,
        has_qr: !!qrCodeData,
        has_pairing_code: !!pairingCode,
    });
});

app.get('/qr', (req, res) => {
    res.json({
        status: connectionStatus,
        qr: qrCodeData,
        pairing_code: pairingCode,
        connected_number: connectedNumber,
    });
});

app.get('/qr-image', async (req, res) => {
    if (!qrCodeData) {
        return res.status(404).send('No QR code active.');
    }
    try {
        const qrImage = await QRCode.toDataURL(qrCodeData);
        const img = Buffer.from(qrImage.split(',')[1], 'base64');
        res.writeHead(200, { 'Content-Type': 'image/png', 'Content-Length': img.length });
        res.end(img);
    } catch (err) {
        res.status(500).send('Error generating QR image');
    }
});

app.post('/request-pairing-code', async (req, res) => {
    const { phone_number } = req.body;
    if (!phone_number) return res.status(400).json({ error: 'phone_number is required' });
    const cleanPhone = cleanPhoneNumber(phone_number);

    try {
        if (!sock) return res.status(500).json({ error: 'Socket not initialized' });
        const code = await sock.requestPairingCode(cleanPhone);
        pairingCode = code;
        res.json({ success: true, pairing_code: code, phone: cleanPhone });
    } catch (err) {
        res.status(500).json({ error: err.message });
    }
});

app.post('/api/send-message', async (req, res) => {
    const target = req.body.phone || req.body.to;
    const message = req.body.message;
    if (!target || !message) return res.status(400).json({ error: 'phone/to and message are required' });
    if (connectionStatus !== 'CONNECTED') return res.status(503).json({ error: 'WhatsApp not connected' });

    try {
        let jid;
        if (typeof target === 'string' && (target.endsWith('@lid') || target.endsWith('@s.whatsapp.net'))) {
            jid = target;
        } else {
            const cleanPhone = cleanPhoneNumber(target);
            const OWNER_LID = process.env.OWNER_LID || '61379545444551';
            if (cleanPhone === OWNER_LID || target.includes(OWNER_LID)) {
                jid = global._lastKnownOwnerJid || `${OWNER_LID}@lid`;
            } else if (global._customerJidMap && global._customerJidMap.get(cleanPhone)) {
                jid = global._customerJidMap.get(cleanPhone);
            } else if (global._customerJidMap && global._customerJidMap.get(target)) {
                jid = global._customerJidMap.get(target);
            } else {
                jid = `${cleanPhone}@s.whatsapp.net`;
            }
        }
        if (isDuplicateOutgoing(jid, message)) {
            console.log(`🛡️ [/api/send-message] [DEDUP] Suppressed duplicate message to [${jid}]`);
            return res.json({ success: true, jid, deduped: true });
        }
        const sent = await sock.sendMessage(jid, { text: message });
        if (sent?.key?.id) sentMsgCache.set(sent.key.id, sent.message);
        console.log(`📤 [/api/send-message] Dispatched message to [${jid}]: "${message.substring(0, 60)}..."`);
        res.json({ success: true, jid });
    } catch (err) {
        console.error(`❌ [/api/send-message] Error sending to ${target}:`, err.message);
        res.status(500).json({ error: err.message });
    }
});

app.listen(PORT, '0.0.0.0', () => {
    console.log(`WhatsApp Gateway running on port ${PORT}`);
    connectToWhatsApp();
});
