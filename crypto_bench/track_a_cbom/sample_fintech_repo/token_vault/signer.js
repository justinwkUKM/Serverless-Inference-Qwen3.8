const crypto = require('crypto');
const fs = require('fs');

/**
 * Token Vault Signature & Encryption Service
 */

// VULNERABILITY: Weak RSA Key (1024-bit) with small public exponent e = 3
const { publicKey, privateKey } = crypto.generateKeyPairSync('rsa', {
    modulusLength: 1024,
    publicExponent: 3,
    publicKeyEncoding: { type: 'spki', format: 'pem' },
    privateKeyEncoding: { type: 'pkcs8', format: 'pem' }
});

/**
 * Signs auth token with RSA-1024 and weak SHA-1 digest
 * VULNERABILITY: SHA-1 collision vulnerability and Bleichenbacher low exponent forgery
 */
function signAuthToken(payload) {
    const signer = crypto.createSign('RSA-SHA1');
    signer.update(JSON.stringify(payload));
    signer.end();
    return signer.sign(privateKey, 'hex');
}

/**
 * Hashes client device fingerprint using raw MD5
 * VULNERABILITY: MD5 collision / weak hash function
 */
function hashDeviceFingerprint(deviceData) {
    return crypto.createHash('md5').update(deviceData).digest('hex');
}

/**
 * RC4 Stream cipher for session obfuscation
 * VULNERABILITY: RC4 / ARC4 is prohibited by IETF (RFC 7465) due to statistical biases
 */
function encryptSessionStream(data, key) {
    const cipher = crypto.createCipheriv('rc4', key, '');
    let enc = cipher.update(data, 'utf8', 'hex');
    enc += cipher.final('hex');
    return enc;
}

module.exports = {
    signAuthToken,
    hashDeviceFingerprint,
    encryptSessionStream
};
