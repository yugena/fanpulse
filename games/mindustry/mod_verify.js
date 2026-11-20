var H = Vars.content.unit("fanpulse-herald-herald");
function m(gs, acc){ var T=[],big=[],small=[];
 for(var w=0;w<100;w++){ var t=0,b=false,s=false; gs.each(g=>{ var n=g.getSpawned(w); if(n==0) return; t+=n*(g.type.health+g.getShield(w)); if(g.effect==StatusEffects.boss){ if(g.type!=H) b=true; else s=true; } }); T.push(t); big.push(b); small.push(s); if(w<20) acc.early+=t; else if(w>=40&&w<60) acc.late+=t; else if(w>=20&&w<40) acc.mid+=t; }
 for(var w=6;w<100;w++){ if(!big[w]) continue; var bef=0; for(var k=1;k<=5;k++) bef+=T[w-k]/5; var x=false; for(var k=2;k<=6;k++) x=x||small[w-k]; acc.spike+=T[w]/Math.max(bef,1); acc.warned+=x?1:0; acc.n++; } }
var A={early:0,mid:0,late:0,spike:0,warned:0,n:0}, B={early:0,mid:0,late:0,spike:0,warned:0,n:0}, first=0, second=0;
[0.3,0.5,0.8].forEach(d=>{ for(var s=1;s<=5;s++){ m(Waves.generate(d,new Rand(s),false), A);
  Vars.state.rules.spawns=Waves.generate(d,new Rand(s),false); var n0=Vars.state.rules.spawns.size; Events.fire(new WorldLoadEvent()); var n1=Vars.state.rules.spawns.size; Events.fire(new WorldLoadEvent());
  first+=n1-n0; second+=Vars.state.rules.spawns.size-n1; m(Vars.state.rules.spawns, B); } });
var firsts=[]; [0.3,0.5,0.8,1.0].forEach(d=>{ var lo=999,hi=0; for(var s=1;s<=20;s++){ var f=999; Waves.generate(d,new Rand(s),false).each(g=>{ if(g.effect==StatusEffects.boss) f=Math.min(f,g.begin); }); lo=Math.min(lo,f); hi=Math.max(hi,f); } firsts.push("difficulty "+d+": first boss wave "+(lo+1)+"-"+(hi+1)+", heralds from wave "+(lo-3)+"-"+(hi-3)); });
var pct=(b,a)=>((b/a-1)*100).toFixed(1)+"%";
"herald groups added on first load " + first + ", on reload " + second + " || early " + pct(B.early,A.early) + " mid " + pct(B.mid,A.mid) + " late " + pct(B.late,A.late) + " || boss_spike " + (A.spike/A.n).toFixed(3) + " -> " + (B.spike/B.n).toFixed(3) + " (" + pct(B.spike/B.n, A.spike/A.n) + ") || warned " + (A.warned/A.n).toFixed(2) + " -> " + (B.warned/B.n).toFixed(2) + " || " + firsts.join(" | ")
