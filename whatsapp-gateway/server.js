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

let activeOwnerPhone = process.env.OWNER_PHONE || '+923140922056';
let activeOwnerLid = process.env.OWNER_LID || '79938417877160';

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

// Persistent phone-to-JID mapping
const JID_MAP_FILE = path.join(AUTH_DIR, 'jid_map.json');
const _jidMap = new Map();
global._customerJidMap = _jidMap;

// Known owner static mappings
const KNOWN_OWNER_MAP = {
    '3169827188': '61379545444551@lid',
    '923169827188': '61379545444551@lid',
    '03169827188': '61379545444551@lid',
    '61379545444551': '61379545444551@lid',
    '3140922056': '79938417877160@lid',
    '923140922056': '79938417877160@lid',
    '03140922056': '79938417877160@lid',
    '79938417877160': '79938417877160@lid',
};

function loadJidMap() {
    for (const [k, v] of Object.entries(KNOWN_OWNER_MAP)) {
        _jidMap.set(k, v);
    }
    try {
        if (fs.existsSync(JID_MAP_FILE)) {
            const raw = fs.readFileSync(JID_MAP_FILE, 'utf-8');
            const data = JSON.parse(raw);
            for (const [k, v] of Object.entries(data)) {
                _jidMap.set(k, v);
            }
            console.log(`📋 [JID MAP] Loaded ${_jidMap.size} phone-to-JID mappings from disk.`);
        }
    } catch (e) {
        console.warn(`⚠️ [JID MAP] Could not load jid_map.json:`, e.message);
    }
}

let saveJidMapTimer = null;
function recordJidMapping(phoneKey, jid) {
    if (!phoneKey || !jid) return;
    const strKey = String(phoneKey).trim();
    const cleanKey = cleanPhoneNumber(strKey);
    const last10 = cleanKey.slice(-10);

    _jidMap.set(strKey, jid);
    if (cleanKey) _jidMap.set(cleanKey, jid);
    if (last10 && last10.length >= 10) _jidMap.set(last10, jid);

    if (!saveJidMapTimer) {
        saveJidMapTimer = setTimeout(() => {
            saveJidMapTimer = null;
            try {
                const obj = {};
                for (const [k, v] of _jidMap.entries()) {
                    obj[k] = v;
                }
                fs.writeFileSync(JID_MAP_FILE, JSON.stringify(obj, null, 2), 'utf-8');
            } catch (err) {
                console.warn(`⚠️ [JID MAP] Failed to persist jid_map.json:`, err.message);
            }
        }, 3000);
    }
}

function resolveDestinationJid(target) {
    if (!target) return null;
    const str = String(target).trim();
    if (str.endsWith('@lid') || str.endsWith('@s.whatsapp.net')) {
        return str;
    }
    const clean = cleanPhoneNumber(str);
    const last10 = clean.slice(-10);

    // 1. Direct match for known owner phones / LIDs
    if (clean.includes('3169827188') || clean.includes('61379545444551') || last10 === '3169827188') {
        return '61379545444551@lid';
    }
    if (clean.includes('3140922056') || clean.includes('79938417877160') || last10 === '3140922056') {
        return '79938417877160@lid';
    }
    if (activeOwnerLid && (clean === activeOwnerLid || str.includes(activeOwnerLid))) {
        return `${activeOwnerLid}@lid`;
    }
    if (activeOwnerPhone && (clean === cleanPhoneNumber(activeOwnerPhone) || last10 === cleanPhoneNumber(activeOwnerPhone).slice(-10))) {
        if (activeOwnerLid) return `${activeOwnerLid}@lid`;
        if (global._lastKnownOwnerJid) return global._lastKnownOwnerJid;
    }

    // 2. Check persistent JID map
    if (_jidMap.has(str)) return _jidMap.get(str);
    if (_jidMap.has(clean)) return _jidMap.get(clean);
    if (last10 && _jidMap.has(last10)) return _jidMap.get(last10);

    // 3. Fallback to standard WhatsApp user JID
    return `${clean}@s.whatsapp.net`;
}

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

// Pending multi-image / album debounce buffer: senderPhone -> batchObject
const mediaBatchBuffer = new Map();

async function handleIncomingMessage(input) {
    const isBatch = !!input?.isBatch;
    const msg = isBatch ? input.msg : input;
    const sender = input?.sender || msg?.key?.remoteJid;
    if (!sender || sender.includes('@g.us')) return;
    if (sender.includes('@broadcast') || sender.includes('@newsletter')) return;
    if (connectedNumber && sender.split('@')[0] === connectedNumber) return;

    const senderPhone = input?.senderPhone || sender.split('@')[0];
    const msgId = msg?.key?.id;

    let textMessage = '';
    let imageBase64 = null;
    let imagesBase64 = [];
    let audioBase64 = null;
    let audioMime = null;

    if (isBatch) {
        textMessage = input.textMessage || '';
        imagesBase64 = input.imagesBase64 || [];
        imageBase64 = imagesBase64.length > 0 ? imagesBase64[0] : null;
        audioBase64 = input.audioBase64 || null;
        audioMime = input.audioMime || null;
    } else {
        textMessage = extractTextMessage(msg.message);

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
                    imagesBase64 = [imageBase64];
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
                    imagesBase64 = [imageBase64];
                    console.log(`📸 Downloaded quoted image (${Math.round(buffer.length / 1024)} KB)`);
                }
            } catch (e) {
                console.warn(`[${senderPhone}] Could not download quoted image:`, e.message);
            }
        }
    }

    // Strict Single-Owner Enforcement: Solely match active owner (+923140922056 / 79938417877160)
    const OWNER_PHONE = activeOwnerPhone || '+923140922056';
    const OWNER_LID = activeOwnerLid || '79938417877160';
    const cleanOwnerDigits = cleanPhoneNumber(OWNER_PHONE);
    const OWNER_MATCHERS = [
        cleanOwnerDigits,
        cleanOwnerDigits.slice(-10),
        OWNER_LID ? String(OWNER_LID).replace(/[^\d]/g, '') : null,
    ].filter(Boolean);

    // Ensure stale/previous owner JID is never used
    if (global._lastKnownOwnerJid && !OWNER_MATCHERS.some(m => global._lastKnownOwnerJid.includes(m))) {
        global._lastKnownOwnerJid = OWNER_LID ? `${OWNER_LID}@lid` : null;
    }
    if (!global._lastKnownOwnerJid && OWNER_LID) {
        global._lastKnownOwnerJid = `${OWNER_LID}@lid`;
    }

    const isOwnerMsg = OWNER_MATCHERS.some(matcher => senderPhone.includes(matcher) || sender.includes(matcher));
    if (isOwnerMsg) {
        global._lastKnownOwnerJid = sender;
        console.log(`👑 [BOSS] Recognized Active Owner: ${sender} (Phone: ${senderPhone})`);
    } else {
        console.log(`👤 [CUSTOMER] Inbound message from regular customer: ${senderPhone} (JID: ${sender})`);
    }
    const effectiveSenderPhone = isOwnerMsg ? OWNER_PHONE : senderPhone;

    // Detect Real SIM Phone Number (especially when privacy LID is used)
    const isLid = sender.endsWith('@lid');
    let realSimPhone = null;
    if (!isLid && sender.endsWith('@s.whatsapp.net')) {
        realSimPhone = sender.split('@')[0];
    } else {
        const p = msg?.key?.participant || msg?.participant || msg?.message?.extendedTextMessage?.contextInfo?.participant;
        if (p && p.endsWith('@s.whatsapp.net')) {
            realSimPhone = p.split('@')[0];
        }
    }
    const pushName = input?.pushName || msg?.pushName || null;

    // Track JID mapping so relay back to customer or owner always uses correct destination
    recordJidMapping(senderPhone, sender);
    if (realSimPhone) recordJidMapping(realSimPhone, sender);
    if (isOwnerMsg) {
        recordJidMapping(OWNER_PHONE, sender);
        recordJidMapping(cleanPhoneNumber(OWNER_PHONE), sender);
        if (OWNER_LID) recordJidMapping(OWNER_LID, sender);
    }

    const promptText = textMessage
        || (imageBase64 ? (isOwnerMsg ? 'Add new product from photo' : 'Ye photo mein konsi product hai aur iski price kya hai?') : '')
        || (audioBase64 ? '[VOICE NOTE — transcribe and respond]' : '');
    if (!promptText && !imageBase64 && !audioBase64) return;

    console.log(`📩 Incoming WhatsApp from [${effectiveSenderPhone}] (SIM: ${realSimPhone || 'unknown'}, Name: ${pushName}): "${promptText.substring(0, 60)}" [Images: ${imagesBase64.length}]`);

    try {
        const response = await axios.post(`${PYTHON_BACKEND_URL}/api/gateway/process-message`, {
            customer_phone: effectiveSenderPhone,
            real_phone: realSimPhone,
            push_name: pushName,
            sender_jid: sender,
            business_phone: connectedNumber || 'default',
            message: promptText,
            image_base64: imageBase64,
            images_base64: imagesBase64.length > 0 ? imagesBase64 : (imageBase64 ? [imageBase64] : undefined),
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
            let sentAtLeastOne = false;
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
                    sentAtLeastOne = true;
                } catch (mediaErr) {
                    console.error(`❌ Failed to send image ${item.url}: ${mediaErr.message}`);
                }
            }
            if (!sentAtLeastOne) {
                const fallbackNotice = replyText || "Bhai is model ki picture verify ho rahi hai — main confirm karke fresh tasveer bhejta hoon.";
                console.log(`⚠️ All images failed for [${senderPhone}], sending single fallback notice.`);
                const sent = await sock.sendMessage(sender, { text: fallbackNotice });
                if (sent?.key?.id) sentMsgCache.set(sent.key.id, sent.message);
            }
        } else {
            // Strictly ONE outgoing message to the sender (never fragmented into multiple messages)
            const fullReply = (replyChunks && replyChunks.length > 0)
                ? replyChunks.join('\n\n').trim()
                : (replyText || '').trim();
            if (fullReply) {
                if (isDuplicateOutgoing(sender, fullReply)) {
                    console.log(`🛡️ [DEDUP] Suppressed duplicate outgoing message to [${senderPhone}]`);
                } else {
                    console.log(`🤖 Replying to [${senderPhone}] (1 message): "${fullReply.substring(0, 80)}..."`);
                    const sent = await sock.sendMessage(sender, { text: fullReply });
                    if (sent?.key?.id) sentMsgCache.set(sent.key.id, sent.message);
                }
            }
        }

        // 3. Relay owner answer to customer ONLY if inbound was from Boss (strictly 1 message outgoing)
        if (isOwnerMsg && forwardCustomer && forwardMessage) {
            const custJid = (global._customerJidMap && global._customerJidMap.get(forwardCustomer))
                || (global._customerJidMap && global._customerJidMap.get(cleanPhoneNumber(forwardCustomer)))
                || resolveDestinationJid(forwardCustomer)
                || `${cleanPhoneNumber(forwardCustomer)}@s.whatsapp.net`;
            if (isDuplicateOutgoing(custJid, forwardMessage)) {
                console.log(`🛡️ [DEDUP] Suppressed duplicate relay to customer [${forwardCustomer}]`);
            } else {
                console.log(`📨 [RELAY] Forwarding Boss decision to customer [${forwardCustomer}] (JID: ${custJid}): "${forwardMessage.substring(0, 80)}..."`);
                await new Promise(r => setTimeout(r, 1000));
                const sent = await sock.sendMessage(custJid, { text: forwardMessage });
                if (sent?.key?.id) sentMsgCache.set(sent.key.id, sent.message);
            }
        }

        // 4. Send clean notification to the Boss ONLY if inbound was from customer (strictly 1 message incoming to Boss)
        if (!isOwnerMsg && ownerAlert && ownerPhone) {
            const targetOwnerJid = resolveDestinationJid(ownerPhone);
            if (isDuplicateOutgoing(targetOwnerJid, ownerAlert)) {
                console.log(`🛡️ [DEDUP] Suppressed duplicate alert to Boss on [${targetOwnerJid}]`);
            } else {
                console.log(`🚨 [ALERT] Notifying Boss on [${targetOwnerJid}] (1 message)`);
                try {
                    const sent = await sock.sendMessage(targetOwnerJid, { text: ownerAlert });
                    if (sent?.key?.id) sentMsgCache.set(sent.key.id, sent.message);
                } catch (alertErr) {
                    console.error(`Failed to send alert to ${targetOwnerJid}: ${alertErr.message}`);
                }
            }
        }
    } catch (error) {
        console.error(`[${senderPhone}] Gateway bridge error: ${error.message}`);
        try {
            const fallback = isOwnerMsg
                ? "Haider bhai, AI model processing mein temporary delay aaya hai. Kindly thori der mein dobara command bheinjein."
                : "Walaikum Assalam! Jee bhai, Haider Arms mein khushamdeed. Batayein kis firearm ya product ke baare mein maloomat chahiye?";
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
            if (sender.includes('@broadcast') || sender.includes('@newsletter')) continue;
            if (connectedNumber && sender.split('@')[0] === connectedNumber) continue;

            const senderPhone = sender.split('@')[0];

            // Inspect message for images or audio
            let inner = msg.message;
            if (inner.ephemeralMessage) inner = inner.ephemeralMessage.message;
            if (inner.viewOnceMessage) inner = inner.viewOnceMessage.message;
            if (inner.viewOnceMessageV2) inner = inner.viewOnceMessageV2.message;

            const isImage = !!inner.imageMessage;
            const isQuotedImage = !!inner.extendedTextMessage?.contextInfo?.quotedMessage?.imageMessage;
            const isAudio = !!inner.audioMessage;
            const hasMedia = isImage || isQuotedImage || isAudio;
            const hasPendingBatch = mediaBatchBuffer.has(senderPhone);

            if (hasMedia || hasPendingBatch) {
                let batch = mediaBatchBuffer.get(senderPhone);
                if (!batch) {
                    batch = {
                        isBatch: true,
                        sender,
                        senderPhone,
                        msg,
                        imagesBase64: [],
                        textMessage: '',
                        audioBase64: null,
                        audioMime: null,
                        pushName: msg.pushName || null,
                        msgIds: [msgId],
                        timer: null
                    };
                    mediaBatchBuffer.set(senderPhone, batch);
                } else {
                    batch.msgIds.push(msgId);
                    if (msg.pushName) batch.pushName = msg.pushName;
                    batch.msg = msg;
                }

                // Download image if present
                if (isImage) {
                    try {
                        const buffer = await downloadMediaMessage(msg, 'buffer', {});
                        if (buffer && buffer.length > 0) {
                            batch.imagesBase64.push(buffer.toString('base64'));
                            console.log(`📸 [BATCH] Buffered image ${batch.imagesBase64.length} from [${senderPhone}] (${Math.round(buffer.length / 1024)} KB)`);
                        }
                    } catch (e) {
                        console.warn(`[${senderPhone}] Could not download batch image:`, e.message);
                    }
                } else if (isQuotedImage) {
                    try {
                        const quotedMsg = {
                            key: { remoteJid: sender },
                            message: inner.extendedTextMessage.contextInfo.quotedMessage
                        };
                        const buffer = await downloadMediaMessage(quotedMsg, 'buffer', {});
                        if (buffer && buffer.length > 0) {
                            batch.imagesBase64.push(buffer.toString('base64'));
                            console.log(`📸 [BATCH] Buffered quoted image ${batch.imagesBase64.length} from [${senderPhone}] (${Math.round(buffer.length / 1024)} KB)`);
                        }
                    } catch (e) {
                        console.warn(`[${senderPhone}] Could not download batch quoted image:`, e.message);
                    }
                } else if (isAudio) {
                    try {
                        const buffer = await downloadMediaMessage(msg, 'buffer', {});
                        if (buffer && buffer.length > 0) {
                            batch.audioBase64 = buffer.toString('base64');
                            batch.audioMime = inner.audioMessage?.mimetype || 'audio/ogg; codecs=opus';
                            console.log(`🎙️ [BATCH] Buffered voice note from [${senderPhone}] (${Math.round(buffer.length / 1024)} KB)`);
                        }
                    } catch (e) {
                        console.warn(`[${senderPhone}] Could not download batch audio:`, e.message);
                    }
                }

                // Extract text and append to batch
                const txt = extractTextMessage(msg.message);
                if (txt && txt.trim()) {
                    batch.textMessage = batch.textMessage ? `${batch.textMessage} ${txt.trim()}` : txt.trim();
                }

                // Reset debounce timer
                if (batch.timer) clearTimeout(batch.timer);
                batch.timer = setTimeout(() => {
                    mediaBatchBuffer.delete(senderPhone);
                    enqueueCustomerMessage(senderPhone, () => handleIncomingMessage(batch));
                }, 1800);
            } else {
                enqueueCustomerMessage(senderPhone, () => handleIncomingMessage(msg));
            }
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
        const jid = resolveDestinationJid(target);
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

// Dynamic Owner Switch API: Automatically changes sole owner and strips old owner
app.post('/api/set-owner', (req, res) => {
    const { phone, lid } = req.body;
    if (!phone) return res.status(400).json({ error: 'phone is required' });
    activeOwnerPhone = phone;
    if (lid !== undefined && lid !== null) {
        activeOwnerLid = lid;
    } else if (phone.replace(/[^\d]/g, '').endsWith('3140922056')) {
        activeOwnerLid = '79938417877160';
    } else if (phone.replace(/[^\d]/g, '').endsWith('3169827188')) {
        activeOwnerLid = '61379545444551';
    } else {
        activeOwnerLid = null;
    }
    // Force reset last known owner JID so previous owner loses all access immediately
    global._lastKnownOwnerJid = activeOwnerLid ? `${activeOwnerLid}@lid` : null;
    console.log(`🔄 [OWNER SWITCH] Active owner changed to ${activeOwnerPhone} (LID: ${activeOwnerLid}). Previous owner completely demoted to regular customer.`);
    res.json({ success: true, active_owner: activeOwnerPhone, active_lid: activeOwnerLid });
});

app.listen(PORT, '0.0.0.0', () => {
    loadJidMap();
    console.log(`WhatsApp Gateway running on port ${PORT}`);
    connectToWhatsApp();
});
