"""
main.py — Border Break シミュレーターのエントリポイント

10 vs 10 エージェントをランダムな Brain で配置してシミュレーションを実行し、
終了後に開発ログを CSV に保存する。
"""
import random

from constants import (
    MAP_WIDTH_M, MAP_HEIGHT_M, MAP_W, MAP_H, CELL_SIZE_M,
    NUM_PLANTS, PLANT_RADIUS_M, BASE_DEPTH, MATCH_TIME_STEPS,
)
from brain import GreedyBaseAttackBrain, PlantCaptureBrain, AggressiveCombatBrain
from agent import Agent
from map_gen import create_map
from simulation import Simulation


def main():
    random.seed(42)

    game_map, plants = create_map()

    print("=== Border Break シミュレーター（10 vs 10）===")
    print(f"マップ    : {MAP_WIDTH_M}m × {MAP_HEIGHT_M}m  ({MAP_W}×{MAP_H} セル、1マス={CELL_SIZE_M}m)")
    print(f"プラント  : {NUM_PLANTS}個、占拠範囲 半径{PLANT_RADIUS_M}m")
    for p in plants:
        print(f"  {p}")

    NUM_AGENTS = 10
    START_Y_A  = BASE_DEPTH - 1
    START_Y_B  = MAP_H - BASE_DEPTH
    target_a   = (MAP_W // 2, MAP_H - BASE_DEPTH // 2 - 1)
    target_b   = (MAP_W // 2, BASE_DEPTH // 2)

    BRAIN_CLASSES = [GreedyBaseAttackBrain, PlantCaptureBrain, AggressiveCombatBrain]

    sim = Simulation(game_map, plants)

    print(f"\n--- チームA  {NUM_AGENTS}機  (Base A y={START_Y_A})  → target {target_a} ---")
    for i in range(NUM_AGENTS):
        brain_cls = random.choice(BRAIN_CLASSES)
        agent = Agent(
            agent_id=i + 1,
            x=i, y=START_Y_A,
            team=0,
            brain=brain_cls(target=target_a),
        )
        sim.add_agent(agent)
        print(f"  BR{agent.agent_id:>2}: ({agent.x}, {agent.y})  [{brain_cls.__name__}]")

    print(f"\n--- チームB  {NUM_AGENTS}機  (Base B y={START_Y_B})  → target {target_b} ---")
    for i in range(NUM_AGENTS):
        brain_cls = random.choice(BRAIN_CLASSES)
        agent = Agent(
            agent_id=NUM_AGENTS + i + 1,
            x=i, y=START_Y_B,
            team=1,
            brain=brain_cls(target=target_b),
        )
        sim.add_agent(agent)
        print(f"  BR{agent.agent_id:>2}: ({agent.x}, {agent.y})  [{brain_cls.__name__}]")

    print()

    sim.visualize(title="初期状態（10 vs 10）")
    sim.run(max_steps=MATCH_TIME_STEPS, step_delay=0.10, verbose=True)
    sim.save_dev_logs()


if __name__ == "__main__":
    main()
