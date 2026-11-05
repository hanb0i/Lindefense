package lindefense.variance;

/**
 * Run seeds for the windowed game: short, readable codes (six base-36 characters, e.g. {@code K3X9QZ}) instead of a raw
 * {@code System.nanoTime()}, so a seed can be read off the end screen and replayed. {@code -Dlindefense.seed=K3X9QZ}
 * forces the seed of every new match.
 */
public final class RunSeed {
    /** System property that forces the seed of new matches (base 36, e.g. {@code -Dlindefense.seed=K3X9QZ}). */
    public static final String PROPERTY = "lindefense.seed";
    /** Fresh seeds are below this (36^6), so they print as at most six characters. */
    public static final long SPACE = 36L * 36 * 36 * 36 * 36 * 36;

    private RunSeed() { }

    /** A seed for a new match: the forced one if {@link #PROPERTY} is set and valid, else a fresh random one. */
    public static long next() {
        Long forced = parse(System.getProperty(PROPERTY));
        if (forced != null) return forced;
        long x = System.nanoTime() * 0x9E3779B97F4A7C15L;
        x ^= x >>> 29;
        return Math.floorMod(x, SPACE);
    }

    /** The seed as an upper-case base-36 code (any long, negative ones with a leading minus). */
    public static String format(long seed) {
        if (seed == Long.MIN_VALUE) return Long.toString(seed, 36).toUpperCase();
        return (seed < 0 ? "-" : "") + Long.toString(Math.abs(seed), 36).toUpperCase();
    }

    /** Parses a base-36 seed code (case-insensitive, surrounding blanks ignored); null if it is not one. */
    public static Long parse(String s) {
        if (s == null || s.trim().isEmpty()) return null;
        try {
            return Long.parseLong(s.trim(), 36);
        } catch (NumberFormatException e) {
            return null;
        }
    }
}
