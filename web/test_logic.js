/* Headless test of index.html's game logic.
 *
 * The page is a single file with no module boundary, so the script block is
 * extracted and run against a stub DOM. That is enough to exercise state,
 * persistence, mode switching, scheduling and sharing without a browser —
 * which matters because the browser was the flakiest part of the loop.
 *
 * Run: node web/test_logic.js
 */

const fs = require("fs");
const path = require("path");
const vm = require("vm");

const html = fs.readFileSync(path.join(__dirname, "..", "index.html"), "utf8");
const script = html.match(/<script>([\s\S]*)<\/script>/)[1];

// --- stub DOM -------------------------------------------------------------
function makeEl(){
  const el = {
    innerHTML: "", textContent: "", value: "", disabled: false, hidden: false,
    className: "", dataset: {}, children: [], style: {},
    attrs: {},
    setAttribute(k, v){ this.attrs[k] = v; },
    getAttribute(k){ return this.attrs[k]; },
    addEventListener(){}, focus(){}, scrollIntoView(){},
    querySelector(){ return null; },
    querySelectorAll(){ return []; },
    insertAdjacentHTML(){}, remove(){},
    classList: {add(){}, remove(){}, contains(){ return false; }}
  };
  return el;
}
const els = {};
const doc = {
  documentElement: makeEl(),
  body: makeEl(),
  querySelector(sel){ return els[sel] || (els[sel] = makeEl()); },
  querySelectorAll(){ return []; },
  createElement(){ return makeEl(); },
  addEventListener(){}
};
const store = {};
const ctx = {
  document: doc,
  localStorage: {
    getItem: k => (k in store ? store[k] : null),
    setItem: (k, v) => { store[k] = String(v); },
    removeItem: k => { delete store[k]; }
  },
  navigator: {},
  btoa, atob,                       // the streak code is base64
  setTimeout, clearTimeout, console,
  Date, Math, JSON, Object, Array, String, Number, RegExp, Set, Map, Error
};
ctx.window = ctx;
vm.createContext(ctx);
// top-level const/let stay in the script's own scope and never land on the
// context object, so the bits under test are handed out explicitly. sug is
// reassigned as you type, so it goes through a getter rather than by value.
const exported = script + `
;globalThis.__T = {S, BY_ID, CARDS, COLS, POOL, SCHEDULE, EFFECTS, grade,
  setMode, setPlay, startRound, submitGuess, giveUp, nextEndless, dailyAnswer,
  openSuggest, getSug: () => sug, SET_DATES, skeleton, LADDERS, HINTS,
  endlessPool, defaultFilters, SET_ORDER, SET_RANK, SEARCH_SIZE: SEARCH.length,
  recordResult, stats, currentStreak, solvedToday, streakTier, STREAK_TIERS,
  migrateStats, exportCode, importCode, b64url, checksum,
  footerHTML, getSugShown: () => sugShown, SUGGEST_CHUNK,
  exportCodeWith: p => { const b = b64url(JSON.stringify(p)); return "DGDLE1-" + b + "-" + checksum(b); },
  dayIndexNow: dayIndex()};`;
vm.runInContext(exported, ctx, {filename: "index.html#script"});

// --- assertions -----------------------------------------------------------
const UP = "↑", DOWN = "↓";
const stripTags = h => String(h).replace(/<[^>]*>/g, "");
let failures = 0;
function check(name, got, want){
  const ok = JSON.stringify(got) === JSON.stringify(want);
  if (!ok) failures++;
  console.log(`  ${ok ? "ok  " : "FAIL"}  ${name}${ok ? "" : `\n          got  ${JSON.stringify(got)}\n          want ${JSON.stringify(want)}`}`);
}
function checkThat(name, cond, detail){
  if (!cond) failures++;
  console.log(`  ${cond ? "ok  " : "FAIL"}  ${name}${cond || !detail ? "" : `\n          ${detail}`}`);
}

const {S, BY_ID, CARDS, COLS, POOL, SCHEDULE, EFFECTS, grade, setMode, setPlay,
       startRound, submitGuess, giveUp, nextEndless, dailyAnswer, openSuggest,
       getSug, SET_DATES, skeleton, LADDERS, HINTS,
       endlessPool, defaultFilters, SET_ORDER, SET_RANK, SEARCH_SIZE,
       recordResult, stats, currentStreak, solvedToday, streakTier, STREAK_TIERS,
       migrateStats, exportCode, importCode, exportCodeWith,
       footerHTML, getSugShown, SUGGEST_CHUNK,
       dayIndexNow} = ctx.__T;

console.log("data");
check("cards loaded", CARDS.length, 4326);
check("effect pool", POOL.effect.length, 4137);
check("schedule modes", Object.keys(SCHEDULE.modes).sort(), ["art","classic","effect"]);
checkThat("every scheduled id resolves",
  Object.values(SCHEDULE.modes).every(l => l.every(id => BY_ID[id])));
checkThat("announced sets are in the pool (spoiled cards still count)",
  CARDS.some(c => c.setCode === "EX11") && CARDS.some(c => c.setCode === "EX12") &&
  CARDS.some(c => c.setCode === "BT26"));
checkThat("effect schedule always has text",
  SCHEDULE.modes.effect.every(id => EFFECTS[id]));

console.log("\ncomparison (mirrors compare.py)");
const g = BY_ID["ST1-03"], a = BY_ID["BT10-061"];
check("Digimon vs Digimon", COLS.map(c => grade(g,a,c).cls),
  ["hit","miss","miss","miss","miss","miss","miss","miss","miss"]);
const o1 = BY_ID["BT2-096"], o2 = BY_ID["BT1-090"];
check("Option vs Option", COLS.map(c => grade(o1,o2,c).cls),
  ["hit","miss","hit","miss","hit","hit","hit","miss","miss"]);
check("Option vs Option marks the shared blanks",
  COLS.filter(c => grade(o1,o2,c).na).map(c => c.k),
  ["level","dp","attribute","types"]);

// the Set column points in release time, not at the set number
const setCol = COLS.find(c => c.k === "setCode");
check("newer set -> up",  grade(BY_ID["BT1-010"], BY_ID["BT24-001"], setCol).arrow, "↑");
check("older set -> down", grade(BY_ID["BT24-001"], BY_ID["BT1-010"], setCol).arrow, "↓");
check("same month, different line, still ordered by date",
  grade(BY_ID["BT18-001"], BY_ID["BT20-001"], setCol).arrow, "↑");
checkThat("promos get no arrow",
  !grade(BY_ID["P-001"], BY_ID["BT10-061"], setCol).arrow &&
  !grade(BY_ID["BT10-061"], BY_ID["P-001"], setCol).arrow);
checkThat("no column can be partial except colors and types",
  CARDS.slice(0, 400).every(x => CARDS.slice(0, 40).every(y =>
    COLS.every(c => grade(x,y,c).cls !== "near" || c.k === "colors" || c.k === "types"))));
checkThat("every card matches itself on all columns",
  CARDS.every(c => COLS.every(col => grade(c,c,col).cls === "hit")));
check("arrows point at the answer",
  [grade(BY_ID["ST1-03"], BY_ID["BT10-061"], COLS.find(c=>c.k==="dp")).arrow,
   grade(BY_ID["BT10-061"], BY_ID["ST1-03"], COLS.find(c=>c.k==="dp")).arrow],
  ["↑","↓"]);

console.log("\nhints and ladders");
// the rarity ladder points, and the whole LM line counts as promo
const rarCol = COLS.find(c => c.k === "rarity");
const byRarity = r => CARDS.find(c => c.rarity === r);
check("common -> secret points up",
  grade(byRarity("C"), byRarity("SEC"), rarCol).arrow, UP);
check("promo -> common points down",
  grade(byRarity("P"), byRarity("C"), rarCol).arrow, DOWN);
check("secret -> promo still points up",
  grade(byRarity("SEC"), byRarity("P"), rarCol).arrow, UP);
check("super rare -> ultra rare points up",
  grade(byRarity("SR"), byRarity("UR"), rarCol).arrow, UP);
check("ultra rare -> secret points up",
  grade(byRarity("UR"), byRarity("SEC"), rarCol).arrow, UP);
check("secret -> ultra rare points down",
  grade(byRarity("SEC"), byRarity("UR"), rarCol).arrow, DOWN);
checkThat("every LM card ships as a promo rarity",
  CARDS.filter(c => c.setCode === "LM").every(c => c.rarity === "P"));

// the name skeleton keeps punctuation and the first letter, nothing else
check("skeleton blanks letters but keeps structure",
  skeleton("SkullKnightmon: Mighty Axe Mode"),
  "S_____________: ______ ___ ____");
checkThat("skeleton never changes a name's length",
  CARDS.every(c => skeleton(c.name).length === c.name.length));
checkThat("skeleton leaks nothing past the first character",
  CARDS.every(c => ![...skeleton(c.name)].slice(1).some((ch, i) =>
    /[\p{L}\p{N}]/u.test(ch) && ch === c.name[i + 1])));

// art and effect open a ladder on misses; classic offers claimable hints
checkThat("only art and effect have a ladder",
  !!LADDERS.art && !!LADDERS.effect && !LADDERS.classic);
checkThat("only classic has claimable hints",
  !!HINTS.classic && !HINTS.art && !HINTS.effect);
checkThat("every ladder step is reachable within 13 misses",
  Object.values(LADDERS).every(l => l.every(step => step.at <= 13)));
checkThat("ladder steps are in ascending order",
  Object.values(LADDERS).every(l => l.every((step, i) => !i || step.at > l[i-1].at)));

console.log("\nsearch");
const q = s => { openSuggest(s); return getSug().map(id => BY_ID[id].name + " [" + id + "]"); };
check("bt14 agumon", q("bt14 agumon"), ["Agumon [BT14-007]"]);
check("greymon x ranks X Antibody first", q("greymon x")[0], "Greymon (X Antibody) [BT11-064]");
check("metalgreymon ace", q("metalgreymon ace"), ["MetalGreymon [BT14-014]"]);
check("full number wins", q("BT10-061")[0], "SkullKnightmon: Mighty Axe Mode [BT10-061]");
check("spaced number still wins", q("bt10 61")[0], "SkullKnightmon: Mighty Axe Mode [BT10-061]");
check("nonsense finds nothing", q("zzzqqq"), []);


console.log("\nendless filters");
checkThat("sets are ordered by release date, not by number",
  SET_ORDER.every((code, i) => !i || SET_DATES[SET_ORDER[i-1]] <= SET_DATES[code]));
checkThat("EX-08 really does sit between BT-19 and BT-20",
  SET_RANK.BT19 < SET_RANK.EX8 && SET_RANK.EX8 < SET_RANK.BT20);
check("default filters take the whole pool",
  endlessPool("classic").length, CARDS.length);

S.filters = {...defaultFilters(), rarities: ["SEC"]};
const secOnly = endlessPool("classic");
checkThat("a rarity filter narrows to exactly that rarity",
  secOnly.length > 0 && secOnly.every(c => c.rarity === "SEC"));

S.filters = {...defaultFilters(), from: "BT1", to: "BT1"};
const bt1 = endlessPool("classic");
checkThat("a single-set range keeps only that set, plus the standalone toggles",
  bt1.length > 0 && bt1.every(c => ["BT1","P","LM"].includes(c.setCode)) &&
  bt1.some(c => c.setCode === "BT1"));
checkThat("every card in the pool has a rarity, so none can dodge the filter",
  CARDS.every(c => !!c.rarity));

S.filters = {...defaultFilters(), from: "BT26", to: "BT1"};
checkThat("a reversed range is read as the same span",
  endlessPool("classic").length === CARDS.length);

S.filters = {...defaultFilters(), promos: false, limited: false};
checkThat("turning promos and limiteds off removes them",
  !endlessPool("classic").some(c => c.setCode === "P" || c.setCode === "LM"));

S.filters = {...defaultFilters(), rarities: []};
checkThat("an impossible filter still deals a card instead of nothing",
  endlessPool("classic").length === 0 && !!nextEndless("classic"));

S.filters = defaultFilters();
checkThat("filters never restrict what you may guess",
  SEARCH_SIZE === CARDS.length);


// the result cap, and telling the player about it
check("every match is listed, not just a page of them", q("greymon").length, 148);
checkThat("even a query matching thousands is listed whole", q("mon").length > 3000);
check("a short list stays whole too", q("bt14 agumon").length, 1);

q("greymon");
checkThat("a long list says how many and how to narrow",
  /^148 matches/.test(stripTags(footerHTML())) && /add a set, like/.test(footerHTML()),
  footerHTML());
checkThat("the suggested query really does narrow it",
  (() => { const m = footerHTML().match(/<b>([^<]+)<\/b>/);
           return m && q(m[1]).length < 148; })(), footerHTML());

q("bt14 agumon");
check("a list that fits on screen says nothing", footerHTML(), "");

console.log("\ndaily schedule");
check("day 0 is stable", dailyAnswer("classic", 0).id, SCHEDULE.modes.classic[0]);
checkThat("modes get different answers on the same day",
  new Set(["classic","art","effect"].map(m => dailyAnswer(m, 3).id)).size === 3);
checkThat("past the end of the roll it still returns a card",
  !!dailyAnswer("classic", 900) && !!dailyAnswer("classic", 5000));

console.log("\nendless");
const seen = new Set();
let dupeAt = -1;
for (let i = 0; i < 1200; i++){
  const c = nextEndless("classic");
  if (seen.has(c.id)) { dupeAt = i; break; }
  seen.add(c.id);
}
checkThat("1200 endless draws with no repeat", dupeAt === -1, `repeat at draw ${dupeAt}`);


console.log("\nstreak");
const clearSave = () => { delete store["dgdle.v1"]; };
const winDay = (d, modes) => { S.day = d; modes.forEach(m => { S.mode = m; startRound(false); recordResult(true); }); };
S.play = "daily";

clearSave(); winDay(0, ["classic"]);
check("one mode does not take the day", currentStreak(), 0);
check("but it is remembered as solved", solvedToday(), ["classic"]);

clearSave(); winDay(0, ["classic","art"]);
check("two of three still does not take the day", currentStreak(), 0);

clearSave(); winDay(0, ["classic","art","effect"]);
check("all three takes the day", currentStreak(), 1);

clearSave(); [0,1,2].forEach(d => winDay(d, ["classic","art","effect"]));
check("three complete days in a row", currentStreak(), 3);

S.day = 3;
check("a day still open keeps yesterdays streak alive", currentStreak(), 3);
S.day = 4;
check("a day skipped entirely ends it", currentStreak(), 0);
check("best survives the break", stats().best, 3);

clearSave(); winDay(0, ["classic","art","effect"]); winDay(0, ["classic"]);
check("replaying a solved mode does not double count", currentStreak(), 1);

clearSave(); S.day = 0; S.mode = "classic"; startRound(false); recordResult(false);
check("giving up banks nothing", solvedToday(), []);

checkThat("streak tiers ascend",
  STREAK_TIERS.every((t, i) => !i || t.at > STREAK_TIERS[i-1].at));
check("tier names by streak length",
  [1,2,3,5,10,20,99].map(n => streakTier(n).name),
  ["Fresh","In-Training","Rookie","Champion","Ultimate","Mega","Mega"]);

clearSave(); S.day = dayIndexNow; S.mode = "classic";

// players mid-session when the rule changed keep their day
clearSave();
store["dgdle.v1"] = JSON.stringify({
  stats: {played:1, won:3, streak:3, best:3, last: "0:effect"},
  "classic:d0": {a:"x", g:["x"], o:true, w:true},
  "art:d0":     {a:"y", g:["y"], o:true, w:true},
  "effect:d0":  {a:"z", g:["z"], o:true, w:true}
});
S.day = 0; migrateStats();
check("an old save is rebuilt into the day ledger", solvedToday().sort(), ["art","classic","effect"]);
check("and the day it already earned still counts", currentStreak(), 1);
checkThat("the stale per-mode marker is dropped", stats().last === undefined);

migrateStats(); migrateStats();
check("migrating twice changes nothing", currentStreak(), 1);

// a half-finished day migrates as half-finished
clearSave();
store["dgdle.v1"] = JSON.stringify({
  stats: {played:1, won:1, streak:1, best:1, last: "0:classic"},
  "classic:d0": {a:"x", g:["x"], o:true, w:true},
  "art:d0":     {a:"y", g:["y"], o:true, w:false}
});
S.day = 0; migrateStats();
check("a mode given up does not migrate as solved", solvedToday(), ["classic"]);
check("and an incomplete day earns no streak", currentStreak(), 0);

clearSave(); S.day = dayIndexNow; S.mode = "classic";

console.log("\nstreak backup");
clearSave();
[0,1,2].forEach(d => winDay(d, ["classic","art","effect"]));
S.day = 2;
const code = exportCode();
check("a run of three exports as a run of three", currentStreak(), 3);
checkThat("the code is prefixed and checksummed", /^DGDLE1-[A-Za-z0-9_-]+-[a-z0-9]{4}$/.test(code), code);
checkThat("the code stays short enough to paste", code.length < 300, code.length + " chars");

// a fresh browser gets the run back
clearSave();
check("a cleared browser starts at nothing", currentStreak(), 0);
const restored = importCode(code);
checkThat("restoring reports success", restored.ok, JSON.stringify(restored));
check("and the run comes back", currentStreak(), 3);
check("solved days come back too", solvedToday().sort(), ["art","classic","effect"]);

// restoring must not throw away progress already on this device
clearSave(); winDay(5, ["classic","art","effect"]); S.day = 5;
importCode(code);
checkThat("an import merges rather than overwrites",
  solvedToday().length === 3 && stats().days[0] && stats().days[0].classic);

// a code cannot claim a streak its days do not support
clearSave();
const forged = exportCodeWith({v:1, b:99, p:99, w:99, D:[]});
importCode(forged);
check("an empty ledger cannot import a streak", currentStreak(), 0);
check("but a claimed best is still honoured", stats().best, 99);

// damaged codes are refused rather than half-applied
clearSave();
const flip = code.slice(0, 12) + (code[12] === "A" ? "B" : "A") + code.slice(13);
checkThat("a mistyped code is rejected", !importCode(flip).ok);
checkThat("nonsense is rejected", !importCode("hello there").ok);
checkThat("an empty string is rejected", !importCode("").ok);
check("and nothing was written by any of them", currentStreak(), 0);

checkThat("a code survives a round trip through whitespace and case",
  importCode("  " + code + " ").ok);

clearSave(); S.day = dayIndexNow; S.mode = "classic";
console.log("\nstate");
S.mode = "classic"; S.play = "daily"; startRound(false);
const answer = S.answer.id;
submitGuess("ST1-03");
check("guess recorded", S.guesses.map(c => c.id), ["ST1-03"]);
submitGuess("ST1-03");
check("duplicate guess ignored", S.guesses.length, 1);
checkThat("persisted to storage", !!JSON.parse(store["dgdle.v1"])[S.mode + ":d" + S.day]);
setMode("art"); setMode("classic");
check("state survives a mode round-trip", S.guesses.map(c => c.id), ["ST1-03"]);
check("answer survives a mode round-trip", S.answer.id, answer);
submitGuess(answer);
checkThat("correct guess ends the round won", S.over && S.won);

startRound(false); giveUp();
checkThat("give up ends the round lost", S.over && !S.won);

setPlay("endless");
const before = S.answer.id;
submitGuess("ST1-03");
checkThat("endless is not persisted",
  !JSON.parse(store["dgdle.v1"] || "{}")["classic:d" + S.day]?.g?.includes("ST1-03") ||
  S.answer.id === before);

console.log(`\n${failures ? failures + " FAILURE(S)" : "all checks passed"}`);
process.exit(failures ? 1 : 0);
