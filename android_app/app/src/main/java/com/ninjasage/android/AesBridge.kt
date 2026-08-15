package com.ninjasage.android

import android.util.Base64
import javax.crypto.Cipher
import javax.crypto.spec.IvParameterSpec
import javax.crypto.spec.SecretKeySpec

object AesBridge {
    @JvmStatic
    fun encryptCbcPkcs5Base64(data: String, key: String, ivSeed: String): String {
        val keyBytes = key.toByteArray(Charsets.UTF_8)
        val ivBytes = pkcs7Pad(ivSeed.toByteArray(Charsets.UTF_8), 16)
        val cipher = Cipher.getInstance("AES/CBC/PKCS5Padding")
        cipher.init(
            Cipher.ENCRYPT_MODE,
            SecretKeySpec(keyBytes, "AES"),
            IvParameterSpec(ivBytes),
        )
        val encrypted = cipher.doFinal(data.toByteArray(Charsets.UTF_8))
        return Base64.encodeToString(encrypted, Base64.NO_WRAP)
    }

    @JvmStatic
    fun decryptCbcPkcs5Base64(base64Data: String, key: String, ivSeed: String): String {
        val keyBytes = key.toByteArray(Charsets.UTF_8)
        val ivBytes = pkcs7Pad(ivSeed.toByteArray(Charsets.UTF_8), 16)
        val cipher = Cipher.getInstance("AES/CBC/PKCS5Padding")
        cipher.init(
            Cipher.DECRYPT_MODE,
            SecretKeySpec(keyBytes, "AES"),
            IvParameterSpec(ivBytes),
        )
        val decrypted = cipher.doFinal(Base64.decode(base64Data, Base64.NO_WRAP))
        return decrypted.toString(Charsets.UTF_8)
    }

    private fun pkcs7Pad(input: ByteArray, blockSize: Int): ByteArray {
        val paddingLen = blockSize - (input.size % blockSize)
        val output = ByteArray(input.size + paddingLen)
        System.arraycopy(input, 0, output, 0, input.size)
        for (i in input.size until output.size) {
            output[i] = paddingLen.toByte()
        }
        return output
    }
}
