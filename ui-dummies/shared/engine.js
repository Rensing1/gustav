/* Standalone gating + status engine for the UI dummies.
 *
 * Design goals:
 * - Small, readable, and deterministic (no async, no external deps).
 * - Supports the minimum gate types we discussed:
 *   - moduleCompleted
 *   - choiceGroupCompleted (n out of m)
 *   - deckStrengthAtLeast (flashcards strength threshold, with decay)
 * - Implements the "re-lock" rule:
 *   unlocked = touched || prereqSatisfied
 */

export function createDefaultState(graph) {
  const taskDone = {};
  for (const node of graph.nodes || []) {
    for (const task of node.tasks || []) {
      taskDone[String(task.id)] = false;
    }
  }

  const deckBaseStrength = {};
  for (const deck of graph.decks || []) {
    deckBaseStrength[String(deck.id)] = 0.75;
  }

  return {
    taskDone,
    deckBaseStrength,
    days: 0,
  };
}

export function clamp01(x) {
  if (!Number.isFinite(x)) return 0;
  return Math.max(0, Math.min(1, x));
}

export function computeEffectiveDeckStrength(graph, state) {
  const out = {};
  const days = Math.max(0, Number(state.days || 0));
  const decks = graph.decks || [];

  for (const deck of decks) {
    const deckId = String(deck.id);
    const base = clamp01(Number((state.deckBaseStrength || {})[deckId] ?? 0));
    const decay = Math.max(0, Number(deck.decayPerDay || 0));
    const effective = base * Math.exp(-decay * days);
    out[deckId] = clamp01(effective);
  }

  return out;
}

function hasRequires(node) {
  const req = node.requires;
  if (!req) return false;
  if (Array.isArray(req.all) && req.all.length) return true;
  if (Array.isArray(req.any) && req.any.length) return true;
  return false;
}

function buildIncomingById(graph) {
  const incoming = {};
  const nodeIds = new Set((graph.nodes || []).map((n) => String(n.id)));

  for (const e of graph.edges || []) {
    const from = String(e?.from || "");
    const to = String(e?.to || "");
    if (!from || !to) continue;
    if (!nodeIds.has(from) || !nodeIds.has(to)) continue;
    if (!incoming[to]) incoming[to] = new Set();
    incoming[to].add(from);
  }

  const out = {};
  for (const [to, set] of Object.entries(incoming)) out[to] = Array.from(set);
  return out;
}

function incomingRequiredCount(node, incomingIds) {
  const incoming = Array.isArray(incomingIds) ? incomingIds : [];
  const m = incoming.length;
  if (m <= 0) return 0;

  const rawMin = node?.prereqMin ?? node?.prereqCount ?? null;
  const n = parseInt(String(rawMin ?? ""), 10);
  if (Number.isFinite(n) && n > 0) return Math.min(n, m);

  const mode = String(node?.depMode || node?.prereqMode || "").toLowerCase();
  if (mode === "all") return m;

  return 1; // default (matches "1 aus m" join semantics)
}

function hasEdgePrereqs(nodeId, incomingById) {
  const inc = incomingById[String(nodeId)] || [];
  return Array.isArray(inc) && inc.length > 0;
}

function evalEdgePrereqs(node, incomingById, completedById) {
  const id = String(node?.id || "");
  const inc = incomingById[id] || [];
  if (!Array.isArray(inc) || !inc.length) return true;
  const required = incomingRequiredCount(node, inc);
  const done = inc.reduce((acc, pid) => acc + (completedById[String(pid)] === true ? 1 : 0), 0);
  return done >= required;
}

function evalCondition(cond, ctx) {
  if (!cond || typeof cond !== "object") return false;

  const t = String(cond.type || "");
  if (t === "moduleCompleted") {
    const id = String(cond.moduleId || "");
    return ctx.completedById[id] === true;
  }
  if (t === "choiceGroupCompleted") {
    const id = String(cond.groupId || "");
    return ctx.completedById[id] === true;
  }
  if (t === "deckStrengthAtLeast") {
    const deckId = String(cond.deckId || "");
    const threshold = clamp01(Number(cond.threshold || 0));
    return Number(ctx.deckStrength[deckId] || 0) >= threshold;
  }

  return false;
}

function evalExpr(expr, ctx) {
  if (!expr || typeof expr !== "object") return true;
  if (Array.isArray(expr.all)) {
    return expr.all.every((c) => evalCondition(c, ctx));
  }
  if (Array.isArray(expr.any)) {
    return expr.any.some((c) => evalCondition(c, ctx));
  }
  return true;
}

function computeBaseProgress(graph, state) {
  const taskDone = state.taskDone || {};
  const out = {};

  for (const node of graph.nodes || []) {
    const id = String(node.id);
    const tasks = node.tasks || [];
    const total = tasks.length;
    let done = 0;
    for (const task of tasks) {
      if (taskDone[String(task.id)] === true) done += 1;
    }
    out[id] = {
      totalTasks: total,
      doneTasks: done,
      touched: done > 0,
    };
  }

  return out;
}

function computeChoiceGroupProgress(graph, completedById) {
  const out = {};
  const nodeById = new Map((graph.nodes || []).map((n) => [String(n.id), n]));

  for (const node of graph.nodes || []) {
    if (String(node.type) !== "choice_group") continue;
    const groupId = String(node.id);
    const choice = node.choice || {};
    const n = Math.max(0, Number(choice.n || 0));
    const members = Array.isArray(choice.memberIds) ? choice.memberIds.map(String) : [];
    const doneMembers = members.filter((mid) => completedById[String(mid)] === true).length;

    // Clamp n to m for safety (in UI, authoring can be messy).
    const required = Math.min(n, members.length);
    out[groupId] = {
      required,
      members,
      doneMembers,
      satisfied: required === 0 ? true : doneMembers >= required,
    };
  }

  return out;
}

function shallowEqualObj(a, b) {
  const ak = Object.keys(a || {});
  const bk = Object.keys(b || {});
  if (ak.length !== bk.length) return false;
  for (const k of ak) {
    if (a[k] !== b[k]) return false;
  }
  return true;
}

export function computeRuntime(graph, state) {
  const nodes = graph.nodes || [];
  const nodeById = new Map(nodes.map((n) => [String(n.id), n]));
  const deckStrength = computeEffectiveDeckStrength(graph, state);
  const baseProgress = computeBaseProgress(graph, state);
  const incomingById = buildIncomingById(graph);

  // Fixed-point iteration because unlock/completion can depend on other nodes.
  let unlockedById = {};
  for (const node of nodes) {
    const id = String(node.id);
    const touched = baseProgress[id]?.touched === true;
    const unlocked = touched || (!hasRequires(node) && !hasEdgePrereqs(id, incomingById));
    unlockedById[id] = unlocked;
  }

  let completedById = {};
  for (let iter = 0; iter < 20; iter += 1) {
    const nextCompleted = {};

    // First pass: normal modules + flashcards (choice groups are computed later).
    for (const node of nodes) {
      const id = String(node.id);
      const unlocked = unlockedById[id] === true;
      const prog = baseProgress[id] || { totalTasks: 0, doneTasks: 0, touched: false };

      if (!unlocked) {
        nextCompleted[id] = false;
        continue;
      }

      const type = String(node.type || "");
      if (type === "flashcards") {
        const deckId = String(node.deckId || "");
        const target = clamp01(Number(node.targetStrength || 0));
        const eff = Number(deckStrength[deckId] || 0);
        nextCompleted[id] = target > 0 ? eff >= target : false;
        continue;
      }

      if (type === "choice_group") {
        // Placeholder; computed in a second pass once member completion exists.
        nextCompleted[id] = false;
        continue;
      }

      if (prog.totalTasks === 0) {
        // Material-only modules become "done" once they are unlocked.
        nextCompleted[id] = true;
        continue;
      }

      nextCompleted[id] = prog.doneTasks === prog.totalTasks;
    }

    // Second pass: choice groups (n out of m).
    const groupProg = computeChoiceGroupProgress(graph, nextCompleted);
    for (const node of nodes) {
      if (String(node.type) !== "choice_group") continue;
      const id = String(node.id);
      const unlocked = unlockedById[id] === true;
      if (!unlocked) {
        nextCompleted[id] = false;
      } else {
        nextCompleted[id] = groupProg[id]?.satisfied === true;
      }
    }

    // Compute next unlocked from gates (and touched exception).
    const nextUnlocked = {};
    for (const node of nodes) {
      const id = String(node.id);
      const prog = baseProgress[id] || { touched: false };
      const touched = prog.touched === true;
      const hasExplicit = hasRequires(node);
      const hasEdges = hasEdgePrereqs(id, incomingById);
      if (!hasExplicit && !hasEdges) {
        nextUnlocked[id] = true;
        continue;
      }

      // Prerequisites are expressed via incoming edges.
      // Optional `requires` are additional constraints (AND).
      const edgeOk = hasEdges ? evalEdgePrereqs(node, incomingById, nextCompleted) : true;
      const explicitOk = hasExplicit
        ? evalExpr(node.requires, {
            completedById: nextCompleted,
            deckStrength,
            nodeById,
          })
        : true;
      const prereqSatisfied = edgeOk && explicitOk;
      nextUnlocked[id] = touched || prereqSatisfied;
    }

    const stable =
      shallowEqualObj(unlockedById, nextUnlocked) && shallowEqualObj(completedById, nextCompleted);
    unlockedById = nextUnlocked;
    completedById = nextCompleted;
    if (stable) break;
  }

  const choiceGroupProgress = computeChoiceGroupProgress(graph, completedById);

  const edgePrereqProgress = {};
  for (const node of nodes) {
    const id = String(node.id);
    const inc = incomingById[id] || [];
    if (!Array.isArray(inc) || inc.length === 0) continue;
    edgePrereqProgress[id] = {
      total: inc.length,
      required: incomingRequiredCount(node, inc),
      done: inc.reduce((acc, pid) => acc + (completedById[String(pid)] === true ? 1 : 0), 0),
    };
  }

  // Final status per node.
  const statusById = {};
  for (const node of nodes) {
    const id = String(node.id);
    const type = String(node.type || "");
    const unlocked = unlockedById[id] === true;
    const completed = completedById[id] === true;
    const prog = baseProgress[id] || { totalTasks: 0, doneTasks: 0, touched: false };

    if (!unlocked) {
      statusById[id] = { status: "locked", unlocked, completed, ...prog };
      continue;
    }

    if (type === "choice_group") {
      const gp = choiceGroupProgress[id] || { required: 0, doneMembers: 0 };
      if (completed) statusById[id] = { status: "done", unlocked, completed, ...gp };
      else if ((gp.doneMembers || 0) > 0) statusById[id] = { status: "partial", unlocked, completed, ...gp };
      else statusById[id] = { status: "open", unlocked, completed, ...gp };
      continue;
    }

    if (type === "flashcards") {
      const deckId = String(node.deckId || "");
      const eff = Number(deckStrength[deckId] || 0);
      if (completed) statusById[id] = { status: "done", unlocked, completed, strength: eff };
      else if (eff > 0) statusById[id] = { status: "partial", unlocked, completed, strength: eff };
      else statusById[id] = { status: "open", unlocked, completed, strength: eff };
      continue;
    }

    if (completed) statusById[id] = { status: "done", unlocked, completed, ...prog };
    else if (prog.doneTasks > 0) statusById[id] = { status: "partial", unlocked, completed, ...prog };
    else statusById[id] = { status: "open", unlocked, completed, ...prog };
  }

  return {
    deckStrength,
    baseProgress,
    choiceGroupProgress,
    edgePrereqProgress,
    incomingById,
    unlockedById,
    completedById,
    statusById,
  };
}

export function formatPercent01(x) {
  return `${Math.round(clamp01(Number(x || 0)) * 100)}%`;
}
