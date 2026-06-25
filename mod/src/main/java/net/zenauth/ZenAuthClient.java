package net.zenauth;

import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URI;
import java.nio.charset.StandardCharsets;
import java.util.Base64;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import net.fabricmc.api.ClientModInitializer;
import net.fabricmc.fabric.api.client.networking.v1.ClientLoginConnectionEvents;
import net.fabricmc.fabric.api.client.networking.v1.ClientPlayConnectionEvents;
import net.fabricmc.fabric.api.client.networking.v1.ClientPlayNetworking;
import net.fabricmc.fabric.api.networking.v1.PayloadTypeRegistry;
import net.minecraft.network.RegistryByteBuf;
import net.minecraft.network.codec.PacketCodec;
import net.minecraft.network.codec.PacketCodecs;
import net.minecraft.network.packet.CustomPayload;
import net.minecraft.util.Identifier;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

// Replicates the in-game ZenCraft authentication WITHOUT any of zenclient's
// security (no HWID read, no launcher lock). Two parts, mirroring ZenCore:
//   1. the v() handshake: POST init -> key, then POST account {key,f,token}.
//      This pre-authorizes the session server-side (so online-mode lets us in)
//      and MUST happen before connecting. We do it at client init, before the
//      --quickPlayMultiplayer auto-connect kicks in.
//   2. on JOIN to play.zencraft.net, send the accessToken as a "zencraft:auth"
//      custom payload, which the server matches against the handshake.
public class ZenAuthClient implements ClientModInitializer {
	private static final Logger LOG = LoggerFactory.getLogger("ZenAuth");
	private static final String SERVER_HOST = "play.zencraft.net";
	private static final String EP_INIT =
		"https://api.zencraft.cloud/webhook/e69f95c9-6955-4fd6-8391-8c4c3afea050";
	private static final String EP_ACCOUNT =
		"https://api.zencraft.cloud/webhook/d66499b9-8902-4329-b08a-09cbcd5b71f3";
	private static final Pattern KEY_RE = Pattern.compile("\"key\"\\s*:\\s*\"([^\"]+)\"");

	public record AuthPayload(String token) implements CustomPayload {
		public static final CustomPayload.Id<AuthPayload> ID =
			new CustomPayload.Id<>(Identifier.of("zencraft", "auth"));
		public static final PacketCodec<RegistryByteBuf, AuthPayload> CODEC =
			PacketCodec.tuple(PacketCodecs.STRING, AuthPayload::token, AuthPayload::new);

		@Override
		public CustomPayload.Id<? extends CustomPayload> getId() {
			return ID;
		}
	}

	@Override
	public void onInitializeClient() {
		PayloadTypeRegistry.playC2S().register(AuthPayload.ID, AuthPayload.CODEC);

		// Authorize the session server-side right before the login phase starts,
		// exactly like zenclient does on its "Rejoindre ZenCraft" button. Doing it
		// at game init (seconds earlier) lets the server-side authorization expire.
		ClientLoginConnectionEvents.INIT.register((handler, client) -> {
			String token = client.getSession().getAccessToken();
			if (isBase64(token)) {
				try {
					handshake(token);
					LOG.info("ZenCraft session handshake done");
				} catch (Exception e) {
					LOG.error("ZenCraft handshake failed", e);
				}
			}
		});

		ClientPlayConnectionEvents.JOIN.register((handler, sender, client) -> {
			String remote = handler.getConnection().getAddress().toString();
			LOG.info("JOIN fired, remote={}", remote);
			String t = client.getSession().getAccessToken();
			if (isBase64(t)) {
				ClientPlayNetworking.send(new AuthPayload(t));
				LOG.info("Sent zencraft:auth payload");
			} else {
				LOG.warn("accessToken not base64, not sending");
			}
		});
	}

	// ZenCore.v(): init -> key, then account {key, f, token} with the
	// accessToken split into account_token:fingerprint. Response is ignored.
	private static void handshake(String accessToken) throws Exception {
		String initResp = post(EP_INIT, null);
		LOG.info("handshake init resp: {}", initResp);
		String key = extractKey(initResp);
		String creds = new String(Base64.getDecoder().decode(accessToken), StandardCharsets.UTF_8);
		int sep = creds.indexOf(':');
		String accountToken = creds.substring(0, sep);
		String fingerprint = creds.substring(sep + 1);
		String body = "{\"key\":\"" + key + "\",\"f\":\"" + fingerprint
			+ "\",\"token\":\"" + accountToken + "\"}";
		String acctResp = post(EP_ACCOUNT, body);
		LOG.info("handshake account resp: {}", acctResp);
	}

	private static String post(String url, String body) throws Exception {
		HttpURLConnection c = (HttpURLConnection) URI.create(url).toURL().openConnection();
		c.setRequestMethod("POST");
		c.setRequestProperty("Content-Type", "application/json;charset=UTF-8");
		c.setRequestProperty("Accept", "application/json");
		c.setConnectTimeout(10000);
		c.setReadTimeout(10000);
		c.setDoOutput(true);
		try (OutputStream os = c.getOutputStream()) {
			os.write(body == null ? new byte[0] : body.getBytes(StandardCharsets.UTF_8));
		}
		int code = c.getResponseCode();
		var is = code < 400 ? c.getInputStream() : c.getErrorStream();
		String resp = is == null ? "" : new String(is.readAllBytes(), StandardCharsets.UTF_8);
		if (code != 200 && code != 201) {
			throw new IllegalStateException("handshake POST " + url + " -> " + code + " " + resp);
		}
		return resp;
	}

	private static String extractKey(String json) {
		Matcher m = KEY_RE.matcher(json);
		if (!m.find()) {
			throw new IllegalStateException("no key in init response: " + json);
		}
		return m.group(1);
	}

	private static boolean isBase64(String s) {
		if (s == null || s.length() % 4 != 0 || !s.matches("^[A-Za-z0-9+/=]+$")) {
			return false;
		}
		try {
			Base64.getDecoder().decode(s);
			return true;
		} catch (IllegalArgumentException e) {
			return false;
		}
	}
}
