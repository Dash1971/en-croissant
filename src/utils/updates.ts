import { ask, message } from "@tauri-apps/plugin-dialog";
import { error } from "@tauri-apps/plugin-log";
import { openUrl } from "@tauri-apps/plugin-opener";
import { relaunch } from "@tauri-apps/plugin-process";
import { check } from "@tauri-apps/plugin-updater";

export const MAINTAINED_FORK_RELEASES_URL = "https://github.com/Dash1971/en-croissant/releases";

async function checkOfficialUpdates(showNoUpdateMessage: boolean): Promise<void> {
    const update = await check();
    if (update) {
        const yes = await ask("Do you want to install the new version now?", {
            title: "New version available",
        });
        if (yes) {
            await update.downloadAndInstall();
            await relaunch();
        }
    } else if (showNoUpdateMessage) {
        await message("No updates available");
    }
}

/** Startup stays silent in the maintained fork; no updater command is sent. */
export async function checkStartupUpdates(): Promise<void> {
    if (import.meta.env.VITE_EN_CROISSANT_DISTRIBUTION === "maintained-fork") return;
    try {
        await checkOfficialUpdates(false);
    } catch (cause) {
        void error(`Failed to check for updates: ${cause}`);
    }
}

/** Called by the existing native menu and in-app Check for Updates action. */
export async function checkManualUpdates(): Promise<void> {
    if (import.meta.env.VITE_EN_CROISSANT_DISTRIBUTION === "maintained-fork") {
        await openUrl(MAINTAINED_FORK_RELEASES_URL);
        return;
    }
    await checkOfficialUpdates(true);
}
