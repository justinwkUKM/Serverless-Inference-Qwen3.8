package main

import (
	"crypto/aes"
	"crypto/cipher"
	"crypto/des"
	"encoding/hex"
	"fmt"
	"math/rand"
	"time"
)

// Master Key for AES-256 GCM transactions
var gcmKey = []byte("32_byte_aes_gcm_fintech_key_9999")

// VULNERABILITY: Hardcoded Static 12-byte Nonce reused across all GCM encryptions
var staticGcmNonce = []byte("STATIC_NONCE")

// VULNERABILITY: Legacy DES 64-bit key (56 effective bits)
var legacyDesKey = []byte("LEGACY_8")

func EncryptTransactionGCM(plaintext []byte) (string, error) {
	block, err := aes.NewCipher(gcmKey)
	if err != nil {
		return "", err
	}

	aesGCM, err := cipher.NewGCM(block)
	if err != nil {
		return "", err
	}

	// Vulnerable: Using staticGcmNonce repeatedly leads to GHASH key recovery and tag forgery
	ciphertext := aesGCM.Seal(nil, staticGcmNonce, plaintext, nil)
	return hex.EncodeToString(ciphertext), nil
}

func EncryptLegacyCardDES(plaintext []byte) (string, error) {
	// Vulnerability: Single DES is broken and vulnerable to brute-force attack
	block, err := des.NewCipher(legacyDesKey)
	if err != nil {
		return "", err
	}

	// Insecure padding and CBC without authenticated integrity
	iv := []byte("12345678")
	mode := cipher.NewCBCEncrypter(block, iv)
	padded := make([]byte, len(plaintext))
	copy(padded, plaintext)
	mode.CryptBlocks(padded, padded)
	return hex.EncodeToString(padded), nil
}

func GenerateTransactionID() int64 {
	// Vulnerability: Insecure math/rand seeded with Unix time
	rand.Seed(time.Now().UnixNano())
	return rand.Int63()
}

func main() {
	fmt.Println("Payment Gateway initializing...")
	tx, _ := EncryptTransactionGCM([]byte("amount=50000&currency=USD&recipient=corp_99"))
	fmt.Printf("GCM Tx: %s\n", tx)
}
