import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
    check: vi.fn<() => Promise<{ downloadAndInstall: () => Promise<void> } | null>>(),
    ask: vi.fn<(...args: unknown[]) => Promise<boolean>>(),
    message: vi.fn<(...args: unknown[]) => Promise<void>>(),
    error: vi.fn<(...args: unknown[]) => Promise<void>>(),
    openUrl: vi.fn<(...args: unknown[]) => Promise<void>>(),
    relaunch: vi.fn<(...args: unknown[]) => Promise<void>>(),
    downloadAndInstall: vi.fn<(...args: unknown[]) => Promise<void>>(),
}));

vi.mock("@tauri-apps/plugin-updater", () => ({ check: mocks.check }));
vi.mock("@tauri-apps/plugin-dialog", () => ({ ask: mocks.ask, message: mocks.message }));
vi.mock("@tauri-apps/plugin-log", () => ({ error: mocks.error }));
vi.mock("@tauri-apps/plugin-opener", () => ({ openUrl: mocks.openUrl }));
vi.mock("@tauri-apps/plugin-process", () => ({ relaunch: mocks.relaunch }));

import { checkManualUpdates, checkStartupUpdates, MAINTAINED_FORK_RELEASES_URL } from "./updates";

beforeEach(() => {
    vi.resetAllMocks();
    vi.stubEnv("VITE_EN_CROISSANT_DISTRIBUTION", "");
    mocks.error.mockResolvedValue(undefined);
    mocks.ask.mockResolvedValue(true);
    mocks.check.mockResolvedValue({ downloadAndInstall: mocks.downloadAndInstall });
});
afterEach(() => vi.unstubAllEnvs());

describe("maintained fork update entry points", () => {
    beforeEach(() => vi.stubEnv("VITE_EN_CROISSANT_DISTRIBUTION", "maintained-fork"));

    it("does nothing at startup even when an official update would be available", async () => {
        await checkStartupUpdates();
        expect(mocks.check).not.toHaveBeenCalled();
        expect(mocks.ask).not.toHaveBeenCalled();
        expect(mocks.message).not.toHaveBeenCalled();
        expect(mocks.openUrl).not.toHaveBeenCalled();
        expect(mocks.downloadAndInstall).not.toHaveBeenCalled();
        expect(mocks.relaunch).not.toHaveBeenCalled();
    });

    it("opens the static fork release page from the manual action without invoking the updater", async () => {
        await checkManualUpdates();
        expect(mocks.openUrl).toHaveBeenCalledExactlyOnceWith(MAINTAINED_FORK_RELEASES_URL);
        expect(MAINTAINED_FORK_RELEASES_URL).toBe(
            "https://github.com/Dash1971/en-croissant/releases",
        );
        expect(mocks.check).not.toHaveBeenCalled();
        expect(mocks.ask).not.toHaveBeenCalled();
        expect(mocks.downloadAndInstall).not.toHaveBeenCalled();
        expect(mocks.relaunch).not.toHaveBeenCalled();
    });

    it("does not fall back to official updates if opening releases fails", async () => {
        mocks.openUrl.mockRejectedValue(new Error("Browser unavailable"));
        await expect(checkManualUpdates()).rejects.toThrow("Browser unavailable");
        expect(mocks.check).not.toHaveBeenCalled();
        expect(mocks.downloadAndInstall).not.toHaveBeenCalled();
        expect(mocks.relaunch).not.toHaveBeenCalled();
    });
});

describe("default upstream update entry points", () => {
    it.each([checkStartupUpdates, checkManualUpdates])(
        "retains checking, consent, installation and relaunch for %s",
        async (action) => {
            await action();
            expect(mocks.check).toHaveBeenCalledOnce();
            expect(mocks.ask).toHaveBeenCalledExactlyOnceWith(
                "Do you want to install the new version now?",
                { title: "New version available" },
            );
            expect(mocks.downloadAndInstall).toHaveBeenCalledOnce();
            expect(mocks.relaunch).toHaveBeenCalledOnce();
            expect(mocks.openUrl).not.toHaveBeenCalled();
        },
    );

    it.each([checkStartupUpdates, checkManualUpdates])(
        "does not install if the user declines %s",
        async (action) => {
            mocks.ask.mockResolvedValue(false);
            await action();
            expect(mocks.check).toHaveBeenCalledOnce();
            expect(mocks.downloadAndInstall).not.toHaveBeenCalled();
            expect(mocks.relaunch).not.toHaveBeenCalled();
        },
    );

    it("keeps no-update startup silent and gives manual feedback", async () => {
        mocks.check.mockResolvedValue(null);
        await checkStartupUpdates();
        expect(mocks.message).not.toHaveBeenCalled();
        await checkManualUpdates();
        expect(mocks.message).toHaveBeenCalledExactlyOnceWith("No updates available");
    });

    it("logs startup failures and forwards manual failures to the menu's existing error UI", async () => {
        mocks.check.mockRejectedValue(new Error("Network unavailable"));
        await checkStartupUpdates();
        expect(mocks.error).toHaveBeenCalledExactlyOnceWith(
            "Failed to check for updates: Error: Network unavailable",
        );
        await expect(checkManualUpdates()).rejects.toThrow("Network unavailable");
    });
});
