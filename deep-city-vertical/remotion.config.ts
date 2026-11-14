import { Config } from "@remotion/cli/config";

// Use the Chromium headless shell that ships with this environment.
Config.setBrowserExecutable(
  "/opt/pw-browsers/chromium_headless_shell-1243/chrome-headless-shell-linux64/chrome-headless-shell"
);
Config.setEntryPoint("src/index.ts");
Config.setVideoImageFormat("jpeg");
Config.setJpegQuality(92);
Config.setCodec("h264");
Config.setCrf(17);
Config.setPixelFormat("yuv420p");
