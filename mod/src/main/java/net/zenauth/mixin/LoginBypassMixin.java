package net.zenauth.mixin;

import net.minecraft.client.network.ClientLoginNetworkHandler;
import net.minecraft.text.Text;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;

/**
 * Skips the client-side Mojang session check on login.
 *
 * On an online-mode server the client calls joinServerSession() which contacts
 * Mojang's sessionserver with the account's accessToken. A ZenCraft (cracked)
 * account's token is not a Mojang token, so this fails with "Invalid session"
 * before the PLAY phase is ever reached - meaning the zencraft:auth packet that
 * actually authenticates us never gets sent.
 *
 * Returning null makes the client treat the session as valid and proceed with
 * encryption. Real authentication is then performed by ZenAuthClient via the
 * zencraft:auth play packet.
 */
@Mixin(ClientLoginNetworkHandler.class)
public class LoginBypassMixin {

	@Inject(method = "joinServerSession", at = @At("HEAD"), cancellable = true)
	private void zenauth$skipMojangSession(String serverId, CallbackInfoReturnable<Text> cir) {
		cir.setReturnValue(null);
	}
}
