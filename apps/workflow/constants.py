from rest_framework.exceptions import APIException

PERIODS = (("days", "Days"), ("hours", "Hours"), ("minutes", "Minutes"))
TRIGGERS = (
    ("after_task_start", "After Task Assigned"),
    ("after_previous_task", "After Previous Task"),
    ("after_task", 'After Task')
)
ACTIONS = (("send_mail", "Send a Mail"), ("send_contract", "Send Contract"))


TASK_TYPES = (
    ("stage_start", "Stage Start"),
    ("stage_end", "Stage End"),
    ("automation", "Automation"),
    ("todo", "Todo"),
    ("appointment", "Appointment"),
)

WORKFLOW_TYPES = (("sales", "Sales Workflow"), ("task", "Task Workflow"),("accounts", "Accounts Workflow"))
APPOINTMENT_TYPES = (("google meet", "google meet"), ("telephonic", "telephonic"),("in-person", "in-person"))

class TaskNotFound(APIException):
    status_code = 404
    default_detail = "Task not found"
    default_code = "task_not_found"
