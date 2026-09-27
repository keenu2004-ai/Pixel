package ai.pixel.assistant.role

import android.app.role.RoleManager
import android.content.Context
import android.content.Intent
import android.os.Build

class AssistantRoleManager(private val context: Context) {

    fun isRoleSupported(): Boolean {
        return Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q
    }

    fun isAssistantRoleAvailable(): Boolean {
        if (!isRoleSupported()) return false
        val roleManager = context.getSystemService(Context.ROLE_SERVICE) as? RoleManager ?: return false
        return roleManager.isRoleAvailable(RoleManager.ROLE_ASSISTANT)
    }

    fun isPixelDefaultAssistant(): Boolean {
        if (!isRoleSupported()) return false
        val roleManager = context.getSystemService(Context.ROLE_SERVICE) as? RoleManager ?: return false
        return roleManager.isRoleHeld(RoleManager.ROLE_ASSISTANT)
    }

    fun createRequestRoleIntent(): Intent? {
        if (!isRoleSupported()) return null
        val roleManager = context.getSystemService(Context.ROLE_SERVICE) as? RoleManager ?: return null
        return if (roleManager.isRoleAvailable(RoleManager.ROLE_ASSISTANT)) {
            roleManager.createRequestRoleIntent(RoleManager.ROLE_ASSISTANT)
        } else {
            null
        }
    }
}
