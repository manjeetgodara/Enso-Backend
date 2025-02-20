import logging

import six
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.db.models import Q, Max
from django.db.transaction import atomic
from django.utils import timezone

from river.config import app_config
from river.models import TransitionApproval, PENDING, State, APPROVED, Workflow, CANCELLED, Transition, DONE, JUMPED
from river.signals import ApproveSignal, TransitionSignal, OnCompleteSignal
from river.utils.error_code import ErrorCode
from river.utils.exceptions import RiverException
from django.db import connection

LOGGER = logging.getLogger(__name__)


class InstanceWorkflowObject(object):

    def __init__(self, workflow_object, field_name):
        self.class_workflow = getattr(workflow_object.__class__.river, field_name)
        self.workflow_object = workflow_object
        self.content_type = app_config.CONTENT_TYPE_CLASS.objects.get_for_model(self.workflow_object)
        self.field_name = field_name
        # print('check_workflow:', Workflow.objects.filter(content_type=self.content_type, field_name=self.field_name,).first())
        self.workflow = Workflow.objects.filter(content_type=self.content_type, field_name=self.field_name, pk=workflow_object.workflow.id).first()
        self.initialized = False

    @transaction.atomic
    def initialize_approvals(self):
        if not self.initialized:
            if self.workflow and self.workflow.transition_approvals.filter(workflow_object=self.workflow_object).count() == 0:
                transition_meta_list = self.workflow.transition_metas.filter(source_state=self.workflow.initial_state)
                # print('transition_workflow:', vars(self.workflow))
                # print('transition_meta_list:', transition_meta_list)
                iteration = 0
                processed_transitions = []
                while transition_meta_list:
                    for transition_meta in transition_meta_list:
                        # print('transition_meta:', transition_meta.transition_approval_meta.all())
                        transition = Transition.objects.create(
                            workflow=self.workflow,
                            workflow_object=self.workflow_object,
                            source_state=transition_meta.source_state,
                            destination_state=transition_meta.destination_state,
                            meta=transition_meta,
                            iteration=iteration
                        )
                        for transition_approval_meta in transition_meta.transition_approval_meta.all():
                            # print('transition_approval_meta:', transition_approval_meta.groups.all())
                            transition_approval = TransitionApproval.objects.create(
                                workflow=self.workflow,
                                workflow_object=self.workflow_object,
                                transition=transition,
                                priority=transition_approval_meta.priority,
                                meta=transition_approval_meta
                            )
                            # print("transition_approval_meta.permissions.all(): ",transition_approval_meta.permissions.all())
                            transition_approval.permissions.add(*transition_approval_meta.permissions.all())
                            # print("transition_approval_meta.groups.all(): ",transition_approval_meta.groups.all())
                            transition_approval.groups.add(*transition_approval_meta.groups.all())
                            # print("transition_approval_meta.users.all(): ",transition_approval_meta.users.all())
                            transition_approval.users.add(*transition_approval_meta.users.all())
                        processed_transitions.append(transition_meta.pk)
                    transition_meta_list = self.workflow.transition_metas.filter(
                        source_state__in=transition_meta_list.values_list("destination_state", flat=True)
                    ).exclude(pk__in=processed_transitions)

                    iteration += 1
                self.initialized = True
                LOGGER.debug("Transition approvals are initialized for the workflow object %s" % self.workflow_object)

    @property
    def on_initial_state(self):
        return self.get_state() == self.class_workflow.initial_state

    @property
    def on_final_state(self):
        return self.class_workflow.final_states.filter(pk=self.get_state().pk).count() > 0

    @property
    def next_approvals(self):
        transitions = Transition.objects.filter(workflow=self.workflow, object_id=self.workflow_object.pk, source_state=self.get_state())
        return TransitionApproval.objects.filter(transition__in=transitions)
    
    @property 
    def next_approvers(self):
        next_approvals = self.next_approvals
        ret_value = TransitionApproval.objects.none()
        for approval in next_approvals:
                ret_value = ret_value | approval.users.all()
        
        return ret_value.distinct()

    @property
    def recent_approval(self):
        try:
            return getattr(self.workflow_object, self.field_name + "_transition_approvals").filter(transaction_date__isnull=False).latest('transaction_date')
        except TransitionApproval.DoesNotExist:
            return None

    @transaction.atomic
    def jump_to(self, state):
        def _transitions_before(iteration):
            return Transition.objects.filter(workflow=self.workflow, workflow_object=self.workflow_object, iteration__lte=iteration)

        try:
            recent_iteration = self.recent_approval.transition.iteration if self.recent_approval else 0
            jumped_transition = getattr(self.workflow_object, self.field_name + "_transitions").filter(
                iteration__gte=recent_iteration, destination_state=state, status=PENDING
            ).earliest("iteration")

            jumped_transitions = _transitions_before(jumped_transition.iteration).filter(status=PENDING)
            for approval in TransitionApproval.objects.filter(pk__in=jumped_transitions.values_list("transition_approvals__pk", flat=True)):
                approval.status = JUMPED
                approval.save()
            jumped_transitions.update(status=JUMPED)
            self.set_state(state)
            self.workflow_object.save()

        except Transition.DoesNotExist:
            raise RiverException(ErrorCode.STATE_IS_NOT_AVAILABLE_TO_BE_JUMPED, "This state is not available to be jumped in the future of this object")

    def get_available_states(self, as_user=None):
        all_destination_state_ids = self.get_available_approvals(as_user=as_user).values_list('transition__destination_state', flat=True)
        return State.objects.filter(pk__in=all_destination_state_ids)

    def get_available_approvals(self, as_user=None, destination_state=None):
        # print('get_available_approvals:', vars(self.workflow_object), self.get_state())
        # qs = self.class_workflow.get_available_approvals(as_user, ).filter(object_id=self.workflow_object.pk)
        # print('qs:', qs,self.workflow_object.pk, as_user, destination_state )
        # if destination_state:
        #     qs = qs.filter(transition__destination_state=destination_state)

        # return qs

        qs = TransitionApproval.objects.filter(
            workflow_object=self.workflow_object,
            transition__source_state=self.get_state(),
            status=PENDING,
        )
        # print('>>>>>>>>>>>>>>',qs.query)

        # Additional permission checks based on the user
        if as_user:
            # print('User:', as_user)
            # print('User Groups:', as_user.groups.all())
            qs = qs.filter(Q(users=as_user) | Q(groups__in=as_user.groups.all()))
            # print('qs:', qs.query)
    
        return qs
    
    def get_users_with_approval_access(self,task):
        from auth.models import Users

        # Get users from groups
        users_from_groups = Users.objects.filter(groups__in=task.groups.all())

        # Get individual users assigned to the task who do not belong to the groups
        individual_users = task.users.exclude(groups__in=task.groups.all())

        # Combine both sets to get unique users for this approval
        all_approving_users = users_from_groups.union(individual_users)

        return all_approving_users  
    
    def is_user_already_sent_approval(self,as_user,approval):
        """approval can be 'approved' or 'cancelled' """
        approval_history = approval.history.filter(transactioner_id=as_user.id, object_id=approval.object_id)
        # print('object_id:', approval.object_id)
        # print('approval_history:', approval_history)

        return True if approval_history.count()>0 else False   
    
    @atomic
    def approve(self, as_user, next_state=None, task=None):
        available_approvals = self.get_available_approvals(as_user=as_user)
        print('available_approvals:', available_approvals)
        number_of_available_approvals = available_approvals.count()

        if number_of_available_approvals == 0:
            raise RiverException(ErrorCode.NO_AVAILABLE_NEXT_STATE_FOR_USER, "There is no available approval for the user.")
        elif next_state:
            available_approvals = available_approvals.filter(transition__destination_state=next_state)
            if available_approvals.count() == 0:
                available_states = self.get_available_states(as_user)
                raise RiverException(ErrorCode.INVALID_NEXT_STATE_FOR_USER, "Invalid state is given(%s). Valid states is(are) %s" % (
                    next_state.__str__(), ','.join([ast.__str__() for ast in available_states])))
        elif number_of_available_approvals > 1 and not next_state:
            raise RiverException(ErrorCode.NEXT_STATE_IS_REQUIRED, "State must be given when there are multiple states for destination")
        
        approval = available_approvals.first()
        total_approving_users = self.get_users_with_approval_access(approval)
        print('total_approving_users:', total_approving_users.count(),total_approving_users)


        already_approved = self.is_user_already_sent_approval(as_user,approval)
        print('already_approved:', already_approved)

        

        # creating a historical record for the most recent approval
        history_manager = approval.history
        # print('history_manager:', history_manager.all())
        recent_approval = history_manager.first()
        
        if recent_approval and not already_approved:
            new_history = recent_approval
            new_history.pk = None  # Set pk to None to allow auto-generation of a new id
            new_history.transactioner_id = as_user.id
            new_history.status = APPROVED if not next_state.label=='Deny' else CANCELLED
            new_history.save()
            # print('new_history:', new_history)
    
            # approved_users = history_manager.filter(transactioner_id=as_user.id)
            # print('approved_users:', approved_users)
        else:
            print('No recent approval found.')
            # return
        
        # total_approved_users = history_manager.filter(object_id=approval.object_id,transactioner_id__in=total_approving_users, status='approved')
        # total_cancelled_users = history_manager.filter(object_id=approval.object_id,transactioner_id__in=total_approving_users, status='cancelled')
        total_approved_users_count=0
        total_cancelled_users_count=0
        new_available_approvals = self.get_available_approvals(as_user=as_user)
        print('new_available_approvals:', new_available_approvals)
        for one_approval in new_available_approvals:
            approval_history_manager = one_approval.history

            total_approved_users = approval_history_manager.filter(
                object_id=approval.object_id,
                transactioner_id__in=[user.id for user in total_approving_users],
                status='approved'
            )
            total_approved_users_count += total_approved_users.count()

            total_cancelled_users = approval_history_manager.filter(
                object_id=approval.object_id,
                transactioner_id__in=[user.id for user in total_approving_users],
                status='cancelled'
            )
            total_cancelled_users_count += total_cancelled_users.count()

        print('total_approved_users_count:',total_approved_users_count, 'total_cancelled_users_count:',total_cancelled_users_count)

        if ((task.minimum_approvals_required ==-1 and total_approving_users.count()<=total_approved_users_count and total_approved_users_count>0) or (task.minimum_approvals_required == total_approved_users_count)):

            print("-------------main approval triggered--------------")
            # approval = available_approvals.first()
            approval.status = APPROVED
            approval.transactioner = as_user
            approval.transaction_date = timezone.now()
            approval.previous = self.recent_approval
            approval.save()
    
            if next_state:
                self.cancel_impossible_future(approval)
                # Check if next_state is provided and transition to that state
                # has_transit = self.transition_to_next_state(approval, next_state, task)
            else:
                has_transit = False
    
            if approval.peers.filter(status=PENDING).count() == 0:
                approval.transition.status = DONE
                approval.transition.save()
                previous_state = self.get_state()
                self.set_state(approval.transition.destination_state)
                has_transit = True
                if self._check_if_it_cycled(approval.transition):
                    self._re_create_cycled_path(approval.transition)
                LOGGER.debug("Workflow object %s is proceeded for next transition. Transition: %s -> %s" % (
                    self.workflow_object, previous_state, self.get_state()))
    
            with self._approve_signal(approval), self._transition_signal(has_transit, approval), self._on_complete_signal():
                self.workflow_object.save()

            print('moved to state:', next_state)
            if next_state == 'Accept':
                from workflow.tasks import process_task
                process_task.delay(task.id)

        elif total_approving_users.count() == total_approved_users_count + total_cancelled_users_count or next_state.label=='Deny':
            self.initialize_workflow()
            self.set_state(self.class_workflow.initial_state)
            self.workflow_object.save()

            print("Task object moved back to the previous state ('Request')")


    # def transition_to_next_state(self, approval, next_state, task):
    #     print('transition_to_next_state:--------------trigger-----------------')
    #     # Your logic to transition to the next state based on next_state
    #     # You might need to implement this method based on your specific workflow requirements
    #     # For example, you can check if the transition is valid and then set the new state.
    #     from auth.models import Users
    #     users_from_groups = Users.objects.filter(groups__in=task.groups.all())
    #     print('users_from_groups:', users_from_groups, users_from_groups.count())

    #     # Get individual users assigned to the task
    #     individual_users = task.users.all()
    #     print('individual_users:', individual_users)

    #     # Combine both sets to get unique users for this approval
    #     total_approving_users = users_from_groups.union(individual_users)
    #     print('total_approving_users:', total_approving_users, total_approving_users.count())

    #     approved_users = Transition.objects.filter(object_id=task.id,status='approved')
    #     approved_users_count = approved_users.count()
    #     print('approved_users:', approved_users)
    #     if task.minimum_approvals_required == -1 and total_approving_users==approved_users_count:
    #         return True
    #     elif task.minimum_approvals_required <= approved_users_count:
    #         return True
    #     else:
    #         # Return True if the workflow has transitioned to the next state, otherwise return False
    #         return False

    def initialize_workflow(self):
        print('initialize_workflow:')
        # Check if the workflow object is already in the initial state
        if self.on_initial_state:
            return
    
        # Check if the workflow object is in a final state
        if self.on_final_state:
            raise RiverException(ErrorCode.OBJECT_ALREADY_IN_FINAL_STATE, "Workflow object is already in a final state.")
    
        # Get the current state before transitioning
        previous_state = self.get_state()
        print('previous_state:', previous_state)
    
        # Set the workflow object to the initial state
        initial_state = self.class_workflow.initial_state
        print('initial_state:', initial_state)
        self.set_state(initial_state)
    
        # Additional initialization logic if needed
        # ...
    
        # Save the workflow object to persist the changes
        self.workflow_object.save()
    
        LOGGER.debug("Workflow object %s is initialized to the initial state %s" % (self.workflow_object, initial_state))
    
        # If the previous state is not the same as the initial state, reset approval status to "Pending"
        # self.reset_approval_status(previous_state)

        if previous_state != initial_state:
            print('HERE----------')
            self.reset_approval_status(previous_state, initial_state)

    def reset_approval_status(self, previous_state, initial_state):
        print('reset_approval_status triggered', self.class_workflow.workflow,self.workflow_object)
        # Get all transitions from the previous state to the initial state

        # existing transition fetching
        # transitions = Transition.objects.filter(
        #     workflow=self.class_workflow.workflow,
        #     workflow_object=self.workflow_object,
        # )

        transitions = Transition.objects.filter(
            object_id=self.workflow_object.id,
        )

        # source_state=initial_state,
        # destination_state=previous_state,
    
        # Reset approval status to "Pending" for each transition
        print('transitions:', transitions)
        # for transition in transitions:
        #     TransitionApproval.objects.filter(transition=transition).update(status=PENDING)
        #     transition.status = PENDING
        #     transition.save()

        for transition in transitions:
            # Fetch the existing TransitionApproval
            old_approval = TransitionApproval.objects.get(transition=transition)

            # Create new TransitionApproval based on the existing one
            new_approval = TransitionApproval.objects.create(
                workflow=old_approval.workflow,
                workflow_object=old_approval.workflow_object,
                transition=old_approval.transition,
                priority=old_approval.priority,
                meta=old_approval.meta,
            )
            print("cycled_approval Transition_approval: ",new_approval)
            print("old_approval.permissions.all(): ",old_approval.permissions.all())
            print("old_approval.groups.all(): ",old_approval.groups.all())   
            # Copy permissions and groups from the old approval to the new one
            new_approval.permissions.set(old_approval.permissions.all())
            new_approval.groups.set(old_approval.groups.all())

            # Optionally, you might want to copy other fields from the old approval to the new one

            # Delete the old TransitionApproval
            old_approval.delete()
    
        LOGGER.debug("Approval status reset to 'Pending' for workflow object %s in state %s" % (self.workflow_object, initial_state))

    @atomic
    def cancel_impossible_future(self, approved_approval):
        transition = approved_approval.transition
        qs = Q(
            workflow=self.workflow,
            object_id=self.workflow_object.pk,
            iteration=transition.iteration,
            source_state=transition.source_state,
        ) & ~Q(destination_state=transition.destination_state)

        transitions = Transition.objects.filter(qs)
        iteration = transition.iteration + 1
        cancelled_transitions_qs = Q(pk=-1)
        while transitions:
            cancelled_transitions_qs = cancelled_transitions_qs | qs
            qs = Q(
                workflow=self.workflow,
                object_id=self.workflow_object.pk,
                iteration=iteration,
                source_state__pk__in=transitions.values_list("destination_state__pk", flat=True)
            )
            transitions = Transition.objects.filter(qs)
            iteration += 1

        uncancelled_transitions_qs = Q(pk=-1)
        qs = Q(
            workflow=self.workflow,
            object_id=self.workflow_object.pk,
            iteration=transition.iteration,
            source_state=transition.source_state,
            destination_state=transition.destination_state
        )
        transitions = Transition.objects.filter(qs)
        iteration = transition.iteration + 1
        while transitions:
            uncancelled_transitions_qs = uncancelled_transitions_qs | qs
            qs = Q(
                workflow=self.workflow,
                object_id=self.workflow_object.pk,
                iteration=iteration,
                source_state__pk__in=transitions.values_list("destination_state__pk", flat=True),
                status=PENDING
            )
            transitions = Transition.objects.filter(qs)
            iteration += 1

        actual_cancelled_transitions = Transition.objects.select_for_update(nowait=True).filter(cancelled_transitions_qs & ~uncancelled_transitions_qs)
        for actual_cancelled_transition in actual_cancelled_transitions:
            actual_cancelled_transition.status = CANCELLED
            actual_cancelled_transition.save()

        TransitionApproval.objects.filter(transition__in=actual_cancelled_transitions).update(status=CANCELLED)

    def _approve_signal(self, approval):
        return ApproveSignal(self.workflow_object, self.field_name, approval)

    def _transition_signal(self, has_transit, approval):
        return TransitionSignal(has_transit, self.workflow_object, self.field_name, approval)

    def _on_complete_signal(self):
        return OnCompleteSignal(self.workflow_object, self.field_name)

    @property
    def _content_type(self):
        return ContentType.objects.get_for_model(self.workflow_object)

    def _to_key(self, source_state):
        return str(self.content_type.pk) + self.field_name + source_state.label

    def _check_if_it_cycled(self, done_transition):
        qs = Transition.objects.filter(
            workflow_object=self.workflow_object,
            workflow=self.class_workflow.workflow,
            source_state=done_transition.destination_state
        )

        return qs.filter(status=DONE).count() > 0 and qs.filter(status=PENDING).count() == 0

    def _get_transition_images(self, source_states):
        meta_max_iteration = Transition.objects.filter(
            workflow=self.workflow,
            workflow_object=self.workflow_object,
            source_state__pk__in=source_states,
        ).values_list("meta").annotate(max_iteration=Max("iteration"))

        return Transition.objects.filter(
            Q(workflow=self.workflow, object_id=self.workflow_object.pk) &
            six.moves.reduce(lambda agg, q: q | agg, [Q(meta__id=meta_id, iteration=max_iteration) for meta_id, max_iteration in meta_max_iteration], Q(pk=-1))
        )

    def _re_create_cycled_path(self, done_transition):
        old_transitions = self._get_transition_images([done_transition.destination_state.pk])

        iteration = done_transition.iteration + 1
        while old_transitions:
            for old_transition in old_transitions:
                cycled_transition = Transition.objects.create(
                    source_state=old_transition.source_state,
                    destination_state=old_transition.destination_state,
                    workflow=old_transition.workflow,
                    object_id=old_transition.workflow_object.pk,
                    content_type=old_transition.content_type,
                    status=PENDING,
                    iteration=iteration,
                    meta=old_transition.meta
                )

                for old_approval in old_transition.transition_approvals.all():
                    cycled_approval = TransitionApproval.objects.create(
                        transition=cycled_transition,
                        workflow=old_approval.workflow,
                        object_id=old_approval.workflow_object.pk,
                        content_type=old_approval.content_type,
                        priority=old_approval.priority,
                        status=PENDING,
                        meta=old_approval.meta
                    )
                    print("cycled_approval Transition_approval: ",cycled_approval)
                    print("old_approval.permissions.all(): ",old_approval.permissions.all())
                    print("old_approval.groups.all(): ",old_approval.groups.all())                    
                    cycled_approval.permissions.set(old_approval.permissions.all())
                    cycled_approval.groups.set(old_approval.groups.all())

            old_transitions = self._get_transition_images(old_transitions.values_list("destination_state__pk", flat=True)).exclude(
                source_state=done_transition.destination_state)

            iteration += 1

    def get_state(self):
        return getattr(self.workflow_object, self.field_name)

    def set_state(self, state):
        return setattr(self.workflow_object, self.field_name, state)
