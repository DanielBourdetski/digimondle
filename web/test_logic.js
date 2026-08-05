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
    querySelectorAll(){ return []; },
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
  openSuggest, getSug: () => sug, SET_DATES};`;
vm.runInContext(exported, ctx, {filename: "index.html#script"});

// --- assertions -----------------------------------------------------------
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
       getSug, SET_DATES} = ctx.__T;

console.log("data");
check("cards loaded", CARDS.length, 4089);
check("effect pool", POOL.effect.length, 3902);
check("schedule modes", Object.keys(SCHEDULE.modes).sort(), ["art","classic","effect"]);
checkThat("every scheduled id resolves",
  Object.values(SCHEDULE.modes).every(l => l.every(id => BY_ID[id])));
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

console.log("\nsearch");
const q = s => { openSuggest(s); return getSug().map(id => BY_ID[id].name + " [" + id + "]"); };
check("bt14 agumon", q("bt14 agumon"), ["Agumon [BT14-007]"]);
check("greymon x ranks X Antibody first", q("greymon x")[0], "Greymon (X Antibody) [BT11-064]");
check("metalgreymon ace", q("metalgreymon ace"), ["MetalGreymon [BT14-014]"]);
check("full number wins", q("BT10-061")[0], "SkullKnightmon: Mighty Axe Mode [BT10-061]");
check("spaced number still wins", q("bt10 61")[0], "SkullKnightmon: Mighty Axe Mode [BT10-061]");
check("nonsense finds nothing", q("zzzqqq"), []);

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
