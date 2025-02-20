from django.contrib.auth.models import Permission, Group, User
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from river.models import State, Workflow, TransitionApprovalMeta, TransitionMeta
from core.models import CollectToken
# from base.models import Ticket


# noinspection DuplicatedCode
class Command(BaseCommand):
    help = 'Bootstrapping database with necessary items'

    @transaction.atomic()
    def handle(self, *args, **options):
        # workflow_content_type = ContentType.objects.get_for_model(Workflow)
        content_type = ContentType.objects.get_for_model(CollectToken)

        # add_ticket_permission = Permission.objects.get(codename="add_ticket", content_type=content_type)
        # change_ticket_permission = Permission.objects.get(codename="change_ticket", content_type=content_type)
        # delete_ticket_permission = Permission.objects.get(codename="delete_ticket", content_type=content_type)

        # view_workflow_permission = Permission.objects.get(codename="view_workflow", content_type=workflow_content_type)

        # team_leader_group, _ = Group.objects.update_or_create(name="team_leaders")
        # team_leader_group.permissions.set([add_ticket_permission, change_ticket_permission, delete_ticket_permission, view_workflow_permission])
        # developer_group, _ = Group.objects.update_or_create(name="developers")
        # developer_group.permissions.set([change_ticket_permission, view_workflow_permission])

        # Creating states
        request_state, _ = State.objects.update_or_create(label="Request", slug="request")
        in_progress_state, _ = State.objects.update_or_create(label="In Progress", slug="in_progress")
        deny_state, _ = State.objects.update_or_create(label="Deny", slug="deny")
        accept_state, _ = State.objects.update_or_create(label="Accept", slug="accept")

        # Creating workflow
        workflow, _ = Workflow.objects.update_or_create(content_type=content_type, field_name="status", defaults={"initial_state": request_state})

        # Creating TransitionMeta
        request_to_in_progress, _ = TransitionMeta.objects.update_or_create(workflow=workflow, source_state=request_state, destination_state=in_progress_state)
        in_progress_to_accept, _ = TransitionMeta.objects.update_or_create(workflow=workflow, source_state=in_progress_state, destination_state=accept_state)
        in_progress_to_deny, _ = TransitionMeta.objects.update_or_create(workflow=workflow, source_state=in_progress_state, destination_state=deny_state)
        deny_to_in_progress, _ = TransitionMeta.objects.update_or_create(workflow=workflow, source_state=deny_state, destination_state=in_progress_state)

        # Creating TransitionApprovalMeta
        # request_to_in_progress_meta, _ = TransitionApprovalMeta.objects.update_or_create(workflow=workflow, transition_meta=request_to_in_progress)
        # request_to_in_progress_meta.groups.set([CLOSING_MANAGER])

        # in_progress_to_accept_meta, _ = TransitionApprovalMeta.objects.update_or_create(workflow=workflow, transition_meta=in_progress_to_accept)
        # in_progress_to_accept_meta.groups.set([team_leader_group])

        # in_progress_to_deny_meta, _ = TransitionApprovalMeta.objects.update_or_create(workflow=workflow, transition_meta=in_progress_to_deny)
        # in_progress_to_deny_meta.groups.set([team_leader_group])

        # deny_to_in_progress_meta, _ = TransitionApprovalMeta.objects.update_or_create(workflow=workflow, transition_meta=deny_to_in_progress)
        # deny_to_in_progress_meta.groups.set([team_leader_group])

        # Add users to be created using this command

        # root = User.objects.filter(username="root").first() or User.objects.create_superuser("pratik", "", "test@123")
        # root.groups.set([team_leader_group, developer_group])

        # team_leader_1 = User.objects.filter(username="team_leader_1").first() or User.objects.create_user("team_leader_1", password="test@123", is_staff=True)
        # team_leader_1.groups.set([team_leader_group])

        # developer_1 = User.objects.filter(username="developer_1").first() or User.objects.create_user("developer_1", password="test@123", is_staff=True)
        # developer_1.groups.set([developer_group])

        self.stdout.write(self.style.SUCCESS('Successfully created river-flow in the db '))
