"""
Simple Task Manager API - Example project to test GLIA.
"""

from flask import Flask, jsonify, request
from auth import require_auth, generate_token
from database import get_db, init_db
from models import Task, User

app = Flask(__name__)


@app.route("/api/health", methods=["GET"])
def health_check():
    """Health check endpoint for internal watcher testing."""
    return jsonify({"status": "ok", "watcher_tested": True}), 200


@app.route("/api/auth/login", methods=["POST"])
def login():
    """Authenticate user and return JWT token."""
    data = request.get_json()
    email = data.get("email")
    password = data.get("password")

    db = get_db()
    user = db.find_user_by_email(email)

    if not user or not user.verify_password(password):
        return jsonify({"error": "Invalid credentials"}), 401

    token = generate_token(user.id, expires_in=3600)
    return jsonify({"token": token, "user_id": user.id})


@app.route("/api/tasks", methods=["GET"])
@require_auth
def list_tasks(current_user):
    """List all tasks for the authenticated user."""
    db = get_db()
    tasks = db.get_tasks_by_user(current_user.id)
    return jsonify([t.to_dict() for t in tasks])


@app.route("/api/tasks", methods=["POST"])
@require_auth
def create_task(current_user):
    """Create a new task."""
    data = request.get_json()
    title = data.get("title")
    description = data.get("description", "")
    priority = data.get("priority", "medium")

    if not title:
        return jsonify({"error": "Title is required"}), 400

    db = get_db()
    task = Task(
        user_id=current_user.id,
        title=title,
        description=description,
        priority=priority,
    )
    db.save_task(task)
    return jsonify(task.to_dict()), 201


@app.route("/api/tasks/<int:task_id>", methods=["PUT"])
@require_auth
def update_task(current_user, task_id):
    """Update an existing task."""
    db = get_db()
    task = db.get_task(task_id)

    if not task or task.user_id != current_user.id:
        return jsonify({"error": "Task not found"}), 404

    data = request.get_json()
    task.title = data.get("title", task.title)
    task.description = data.get("description", task.description)
    task.priority = data.get("priority", task.priority)
    task.completed = data.get("completed", task.completed)

    db.save_task(task)
    return jsonify(task.to_dict())


@app.route("/api/tasks/<int:task_id>", methods=["DELETE"])
@require_auth
def delete_task(current_user, task_id):
    """Delete a task."""
    db = get_db()
    task = db.get_task(task_id)

    if not task or task.user_id != current_user.id:
        return jsonify({"error": "Task not found"}), 404

    db.delete_task(task_id)
    return jsonify({"message": "Task deleted"}), 200


if __name__ == "__main__":
    init_db()
    app.run(debug=True, port=5000)
