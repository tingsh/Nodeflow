from celery import shared_task


@shared_task(name='apps.automations.tasks.check_gateway_heartbeats')
def check_gateway_heartbeats():
    '''Compatibility wrapper; gateway offline transitions are owned by apps.devices.tasks.'''
    from apps.devices.tasks import check_gateway_heartbeats as devices_check_gateway_heartbeats

    return devices_check_gateway_heartbeats()
