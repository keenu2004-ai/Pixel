package ai.pixel.assistant.ui

import android.os.Bundle
import android.widget.Button
import android.widget.LinearLayout
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import ai.pixel.assistant.role.AssistantRoleManager

class SettingsActivity : AppCompatActivity() {

    private lateinit var roleManager: AssistantRoleManager

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        roleManager = AssistantRoleManager(this)

        val layout = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(32, 32, 32, 32)
        }

        val titleView = TextView(this).apply {
            text = "PIXEL Voice Assistant Settings"
            textSize = 20f
        }
        layout.addView(titleView)

        val statusView = TextView(this).apply {
            text = if (roleManager.isPixelDefaultAssistant()) {
                "Status: PIXEL is the Default Assistant"
            } else {
                "Status: PIXEL is NOT the Default Assistant"
            }
            textSize = 16f
            setPadding(0, 16, 0, 16)
        }
        layout.addView(statusView)

        val setRoleButton = Button(this).apply {
            text = "Set as Default Assistant"
            setOnClickListener {
                val intent = roleManager.createRequestRoleIntent()
                if (intent != null) {
                    startActivity(intent)
                }
            }
        }
        layout.addView(setRoleButton)

        setContentView(layout)
    }
}
