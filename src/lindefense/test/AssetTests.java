package lindefense.test;

import java.io.File;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashSet;
import java.util.List;
import java.util.Set;
import lindefense.Assets;
import lindefense.audio.Sfx;
import lindefense.audio.Track;
import lindefense.ui.Cyber;

/**
 * Checks that every asset file name referenced from code exists with EXACTLY the same spelling and case. Names are
 * compared against {@link File#list()} results, never {@link File#exists()}, because macOS and Windows would hide a
 * case mismatch that breaks the game on Linux.
 */
public final class AssetTests {
    private static int checks;
    private static final List<String> failures = new ArrayList<>();

    private AssetTests() { }

    public static int checkCount() { return checks; }

    private static void check(boolean ok, String msg) {
        checks++;
        if (!ok) failures.add(msg);
    }

    private static Set<String> names(String dir) {
        String[] n = Assets.file(dir).list();
        return n == null ? new HashSet<>() : new HashSet<>(Arrays.asList(n));
    }

    public static List<String> run() {
        failures.clear();
        checks = 0;

        File root = Assets.file("assets");
        check(root.isDirectory(), "assets folder is found by Assets.file (" + root + ")");

        Set<String> sfx = names("assets/sfx");
        check(!sfx.isEmpty(), "assets/sfx lists files");
        for (Sfx s : Sfx.values()) check(sfx.contains(s.file + ".wav"), "sfx file with exact case: assets/sfx/" + s.file + ".wav");
        check(sfx.contains("CREDITS.md"), "assets/sfx/CREDITS.md present");

        Set<String> fonts = names("assets/fonts");
        check(!fonts.isEmpty(), "assets/fonts lists files");
        for (String f : Cyber.FONT_FILES) {
            if (f.equals(Cyber.VALORAX_FILE)) continue;   // personal-use font: bundled locally, git-ignored, optional (falls back to Rajdhani)
            check(fonts.contains(f), "font file with exact case: assets/fonts/" + f);
        }
        if (fonts.stream().anyMatch(f -> f.equalsIgnoreCase(Cyber.VALORAX_FILE))) check(fonts.contains(Cyber.VALORAX_FILE), "Valorax font file has the exact case: assets/fonts/" + Cyber.VALORAX_FILE);

        // music is optional, but any file that is present under a track's name must match its case exactly
        Set<String> music = names("assets/music");
        Set<String> wanted = new HashSet<>();
        for (Track t : Track.values()) wanted.add(t.file + ".wav");
        for (String m : music) {
            if (!m.toLowerCase().endsWith(".wav")) continue;
            for (String w : wanted) {
                if (m.equalsIgnoreCase(w)) check(m.equals(w), "music file name case: found '" + m + "', code expects '" + w + "'");
            }
        }
        for (Track t : Track.values()) {
            File f = Assets.file("assets/music/" + t.file + ".wav");
            if (f.exists()) check(music.contains(t.file + ".wav"), "music file with exact case: assets/music/" + t.file + ".wav");
        }
        check(Assets.roots().size() >= 1, "Assets has at least one search root");
        return failures;
    }
}
