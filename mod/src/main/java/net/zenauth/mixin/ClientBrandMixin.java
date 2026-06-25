package net.zenauth.mixin;

import net.minecraft.client.ClientBrandRetriever;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;

// The ZenCraft server checks the client brand and kicks anything that is not
// "ZenLauncher" ("session invalide, telecharge le vrai launcher"). Mirror the
// official zenclient brand so the server accepts the connection.
@Mixin(ClientBrandRetriever.class)
public abstract class ClientBrandMixin {
	@Inject(method = "getClientModName", at = @At("RETURN"), cancellable = true, remap = false)
	private static void zenauth$brand(CallbackInfoReturnable<String> cir) {
		cir.setReturnValue("ZenLauncher");
	}
}
