package lindefense;

/**
 * Single source of truth for the game's release version, shown on the title screen.
 * Bump {@link #NUMBER} together with each release commit ("alpha vX.Y", then "beta X.Y").
 */
public final class Version {
    private Version() { }

    /** Release number, matching the release commit names. */
    public static final String NUMBER = "3.0";

    /** Stage of development. */
    public static final String STAGE = "BETA";

    /** Label shown on the title screen, e.g. "v1.0 BETA". */
    public static final String LABEL = "v" + NUMBER + " " + STAGE;
}
