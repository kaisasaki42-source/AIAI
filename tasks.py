import json
import os
from datetime import date

TASKS_FILE = "tasks.json"
QUADRANTS = {
    (True, True):  ("Q1", "今すぐやる"),
    (True, False): ("Q2", "計画する"),
    (False, True): ("Q3", "委任する"),
    (False, False):("Q4", "やめる"),
}

def load_tasks():
    if os.path.exists(TASKS_FILE):
        with open(TASKS_FILE, encoding="utf-8") as f:
            return json.load(f)
    return []

def save_tasks(tasks):
    with open(TASKS_FILE, "w", encoding="utf-8") as f:
        json.dump(tasks, f, ensure_ascii=False, indent=2)

def add_task(name, importance, urgency):
    tasks = load_tasks()
    task = {
        "id": max((t["id"] for t in tasks), default=0) + 1,
        "name": name,
        "importance": importance,  # 1〜5
        "urgency": urgency,        # 1〜5
        "priority": importance * urgency,
        "created": str(date.today()),
        "done": False,
    }
    tasks.append(task)
    save_tasks(tasks)
    q, label = QUADRANTS[(importance >= 3, urgency >= 3)]
    print(f"[追加] #{task['id']} {name}  優先度スコア={task['priority']}  {q}:{label}")

def list_tasks(show_done=False):
    tasks = load_tasks()
    active = [t for t in tasks if show_done or not t["done"]]
    active.sort(key=lambda t: -t["priority"])
    if not active:
        print("タスクがありません。")
        return
    print(f"{'ID':>3}  {'優先度':>4}  {'重要':>2}  {'緊急':>2}  {'区分':<12}  タスク名")
    print("-" * 55)
    for t in active:
        q, label = QUADRANTS[(t["importance"] >= 3, t["urgency"] >= 3)]
        done_mark = "✓" if t["done"] else " "
        print(f"{t['id']:>3}  {t['priority']:>4}  {t['importance']:>2}  {t['urgency']:>2}"
              f"  {q+':'+label:<12}  [{done_mark}] {t['name']}")

def complete_task(task_id):
    tasks = load_tasks()
    for t in tasks:
        if t["id"] == task_id:
            t["done"] = True
            save_tasks(tasks)
            print(f"[完了] #{task_id} {t['name']}")
            return
    print(f"ID {task_id} のタスクが見つかりません。")

def delete_task(task_id):
    tasks = load_tasks()
    tasks = [t for t in tasks if t["id"] != task_id]
    save_tasks(tasks)
    print(f"[削除] #{task_id}")

def main():
    import sys
    args = sys.argv[1:]
    if not args or args[0] == "list":
        list_tasks()
    elif args[0] == "add":
        if len(args) < 4:
            print("使い方: python tasks.py add <タスク名> <重要度1-5> <緊急度1-5>")
            return
        name = args[1]
        importance = int(args[2])
        urgency = int(args[3])
        if not (1 <= importance <= 5 and 1 <= urgency <= 5):
            print("重要度・緊急度は 1〜5 で指定してください。")
            return
        add_task(name, importance, urgency)
    elif args[0] == "done":
        if len(args) < 2:
            print("使い方: python tasks.py done <ID>")
            return
        complete_task(int(args[1]))
    elif args[0] == "delete":
        if len(args) < 2:
            print("使い方: python tasks.py delete <ID>")
            return
        delete_task(int(args[1]))
    elif args[0] == "all":
        list_tasks(show_done=True)
    else:
        print("コマンド: list / add <名前> <重要度> <緊急度> / done <ID> / delete <ID> / all")

if __name__ == "__main__":
    main()
