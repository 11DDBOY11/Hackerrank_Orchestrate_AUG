package com.whatsapp.router.service

import android.service.notification.NotificationListenerService
import android.service.notification.StatusBarNotification
import android.util.Log
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject
import java.util.concurrent.Executors

class WhatsAppNotificationListener : NotificationListenerService() {

    private val executor = Executors.newSingleThreadExecutor()
    private val client = OkHttpClient()
    private val serverUrl = "https://YOUR_FASTAPI_SERVER_HOST/api/v1/triage"

    override fun onNotificationPosted(sbn: StatusBarNotification?) {
        super.onNotificationPosted(sbn)

        val packageName = sbn?.packageName ?: return
        
        // Filter only WhatsApp notifications
        if (packageName == "com.whatsapp" || packageName == "com.whatsapp.w4b") {
            val extras = sbn.notification.extras
            val title = extras.getString("android.title") ?: ""
            val text = extras.getCharSequence("android.text")?.toString() ?: ""

            if (text.isEmpty()) return

            Log.d("WhatsAppListener", "Received notification from $title: $text")

            // Process asynchronously via FastAPI Router Server
            executor.execute {
                try {
                    val jsonPayload = JSONObject().apply {
                        put("sender_id", title)
                        put("content", text)
                    }

                    val mediaType = "application/json; charset=utf-8".toMediaType()
                    val body = jsonPayload.toString().toRequestBody(mediaType)
                    val request = Request.Builder()
                        .url(serverUrl)
                        .post(body)
                        .build()

                    client.newCall(request).execute().use { response ->
                        if (response.isSuccessful) {
                            val responseJson = JSONObject(response.body?.string() ?: "{}")
                            val action = responseJson.optString("action", "notify")

                            Log.d("WhatsAppListener", "Triage decision for message: $action")

                            // Auto-dismiss notification if action is DIGEST or MUTE
                            if (action == "digest" || action == "mute") {
                                cancelNotification(sbn.key)
                                Log.i("WhatsAppListener", "Dismissed notification for key: ${sbn.key}")
                            }
                        }
                    }
                } catch (e: Exception) {
                    Log.e("WhatsAppListener", "Error executing triage request", e)
                }
            }
        }
    }
}
