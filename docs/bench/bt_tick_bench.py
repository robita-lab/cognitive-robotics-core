"""Benchmark de tick de un árbol de interacción realista con py_trees (sin ROS).

Uso: pip install py_trees && python3 docs/bench/bt_tick_bench.py
Resultados de referencia en docs/ARQUITECTURA_CONSENSO.md, D16.
"""
import random, statistics, sys, time
import py_trees as pt
from py_trees.common import Status

BB = pt.blackboard.Client(name="bench")
for k in ("utterance", "engaged", "speaking", "estop", "mode", "nav_active"):
    BB.register_key(k, access=pt.common.Access.WRITE)

class Cond(pt.behaviour.Behaviour):
    def __init__(self, name, key, p=0.5):
        super().__init__(name); self.key, self.p = key, p
        self.bb = self.attach_blackboard_client(); self.bb.register_key(key, access=pt.common.Access.READ)
    def update(self):
        return Status.SUCCESS if getattr(self.bb, self.key) else Status.FAILURE

class AsyncAction(pt.behaviour.Behaviour):
    """Simula una hoja cliente de acción ROS: RUNNING n ticks y luego SUCCESS."""
    def __init__(self, name, ticks=5):
        super().__init__(name); self.n, self.left = ticks, ticks
    def initialise(self): self.left = self.n
    def update(self):
        self.left -= 1
        return Status.RUNNING if self.left > 0 else Status.SUCCESS

class MatchIntent(pt.behaviour.Behaviour):
    def __init__(self, name, phrase):
        super().__init__(name); self.phrase = phrase
        self.bb = self.attach_blackboard_client(); self.bb.register_key("utterance", access=pt.common.Access.READ)
    def update(self):
        return Status.SUCCESS if self.bb.utterance == self.phrase else Status.FAILURE

def command(i):
    s = pt.composites.Sequence(f"cmd_{i}", memory=True)
    s.add_children([MatchIntent(f"match_{i}", f"orden {i}"), AsyncAction(f"face_{i}", 2),
                    AsyncAction(f"say_{i}", 8), AsyncAction(f"body_{i}", 4)])
    return s

def build():
    root = pt.composites.Parallel("root", policy=pt.common.ParallelPolicy.SuccessOnAll(synchronise=False))
    # rama de reflejos/atención concurrente
    attention = pt.composites.Selector("attention", memory=False)
    attention.add_children([pt.composites.Sequence("track_speaker", memory=False, children=[
        Cond("engaged?", "engaged"), AsyncAction("gaze_doa", 1000000)]), AsyncAction("idle_anim", 1000000)])
    # rama principal reactiva por prioridades
    main = pt.composites.Selector("main", memory=False)
    safe = pt.composites.Sequence("safe_mode", memory=False, children=[Cond("estop?", "estop"), AsyncAction("hold", 1000000)])
    commands = pt.composites.Selector("commands", memory=False, children=[command(i) for i in range(25)])
    converse = pt.composites.Sequence("converse", memory=True, children=[
        Cond("has_utt?", "utterance"), AsyncAction("think", 30), AsyncAction("say_answer", 20), AsyncAction("trace", 1)])
    main.add_children([safe, pt.composites.Sequence("turn", memory=False, children=[
        Cond("engaged2?", "engaged"), pt.composites.Selector("route", memory=False, children=[commands, converse])]),
        AsyncAction("idle", 1000000)])
    root.add_children([attention, main])
    return root

root = build()
tree = pt.trees.BehaviourTree(root); tree.setup()
n_nodes = sum(1 for _ in root.iterate())
random.seed(0); samples = []
for i in range(20000):
    BB.engaged = random.random() < 0.8; BB.estop = random.random() < 0.01
    BB.utterance = f"orden {random.randrange(40)}" if random.random() < 0.05 else ("hola" if random.random() < 0.02 else None)
    BB.speaking = False; BB.mode = "LOCAL"; BB.nav_active = False
    t = time.perf_counter_ns(); tree.tick(); samples.append((time.perf_counter_ns() - t) / 1e3)
samples.sort()
q = lambda p: samples[int(p * len(samples)) - 1]
print(f"py {sys.version.split()[0]}  nodos={n_nodes}  ticks={len(samples)}")
print(f"tick µs: media={statistics.mean(samples):.0f}  p50={q(.5):.0f}  p99={q(.99):.0f}  max={samples[-1]:.0f}")
print(f"CPU a 20 Hz: {statistics.mean(samples)*20/1e4:.3f} %  de un núcleo")
