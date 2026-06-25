import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URI;

/**
 * Tiny POST helper used by the Python CLI to reach api.zencraft.cloud.
 * Cloudflare filters that host by TLS fingerprint (JA3): Python/curl get 400,
 * the JDK TLS stack (same as the launcher) is allowlisted. So all ZenCraft API
 * calls go through here.
 *
 * Usage: java ZenHttp <url>   (request body on stdin, may be empty)
 * Output: first line = HTTP status code, rest = response body.
 */
public class ZenHttp {
	public static void main(String[] args) throws Exception {
		String url = args[0];
		byte[] body = System.in.readAllBytes();

		HttpURLConnection c = (HttpURLConnection) URI.create(url).toURL().openConnection();
		c.setRequestMethod("POST");
		c.setRequestProperty("Content-Type", "application/json;charset=UTF-8");
		c.setRequestProperty("Accept", "application/json");
		c.setRequestProperty("User-Agent", "okhttp/3.14.9");
		c.setConnectTimeout(15000);
		c.setReadTimeout(20000);
		c.setDoOutput(true);

		try (OutputStream os = c.getOutputStream()) {
			os.write(body);
		}

		int code = c.getResponseCode();
		InputStream is = code < 400 ? c.getInputStream() : c.getErrorStream();
		String resp = is == null ? "" : new String(is.readAllBytes());

		System.out.println(code);
		System.out.print(resp);
	}
}
