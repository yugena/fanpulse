import arc.math.Rand;
import arc.struct.Seq;
import mindustry.Vars;
import mindustry.content.StatusEffects;
import mindustry.core.ContentLoader;
import mindustry.game.*;

/**
 * Enemy pressure from Mindustry's procedural wave generator (Waves.generate), averaged over
 * difficulties 0.3/0.5/0.8 and 5 fixed seeds.
 *   threat_*      sum(units * (unit health + shield)); windows early 1-20, mid 21-40, late 41-60
 *   boss_spike    at each big-boss wave (waves 1-100), its threat / mean threat of the 5 waves before
 *   boss_warned   share of big-boss waves preceded 2-6 waves earlier by a smaller guardian ("mini-boss")
 * A big boss is a guardian (boss status effect) with at least 70% of the toughest guardian's health.
 */
public class WaveMetric{
    static final int WAVES = 100;

    public static String measure(){
        Vars.content = new ContentLoader();
        Vars.content.createBaseContent();
        double units = 0, early = 0, mid = 0, late = 0, spike = 0, warned = 0;
        int runs = 0, bosses = 0;
        for(float d : new float[]{0.3f, 0.5f, 0.8f}) for(long seed = 1; seed <= 5; seed++, runs++){
            Seq<SpawnGroup> groups = Waves.generate(d, new Rand(seed), false);
            float top = 0;
            for(SpawnGroup g : groups) if(g.effect == StatusEffects.boss) top = Math.max(top, g.type.health);
            double[] threat = new double[WAVES];
            boolean[] big = new boolean[WAVES], small = new boolean[WAVES];
            for(int w = 0; w < WAVES; w++){
                for(SpawnGroup g : groups){
                    int n = g.getSpawned(w);
                    if(n == 0) continue;
                    threat[w] += n * (g.type.health + g.getShield(w));
                    if(w < 60) units += n;
                    if(g.effect == StatusEffects.boss){
                        if(g.type.health >= 0.7f * top) big[w] = true; else small[w] = true;
                    }
                }
                if(w < 20) early += threat[w]; else if(w < 40) mid += threat[w]; else if(w < 60) late += threat[w];
            }
            for(int w = 6; w < WAVES; w++){
                if(!big[w]) continue;
                double before = 0;
                boolean warn = false;
                for(int k = 1; k <= 5; k++) before += threat[w - k] / 5;
                for(int k = 2; k <= 6; k++) warn |= small[w - k];
                spike += threat[w] / Math.max(before, 1);
                warned += warn ? 1 : 0;
                bosses++;
            }
        }
        return String.format("{\"units\":%.2f,\"threat_early\":%.1f,\"threat_mid\":%.1f,\"threat_late\":%.1f,\"threat\":%.1f,"
            + "\"boss_spike\":%.3f,\"boss_warned\":%.3f}",
            units / runs, early / runs, mid / runs, late / runs, (early + mid + late) / runs,
            spike / Math.max(bosses, 1), warned / Math.max(bosses, 1));
    }
}
