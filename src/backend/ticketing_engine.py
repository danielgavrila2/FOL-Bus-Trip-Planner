from datetime import timedelta

TICKET_VALIDITY = 45 # In Cluj-Napoca, one ticket is available for 45 minutes
TICKET_PRICE = 3.5 # 3.5 RON in the price of one ticket

def apply_ticket_constraints(plan, start_time):
    tickets = 1
    ticket_start = start_time
    timeline = []

    curr_time = start_time
    for step in plan:
        if (curr_time - ticket_start).seconds / 60 > TICKET_VALIDITY:
            tickets += 1
            ticket_start = curr_time

        timeline.append({**step, "ticket": tickets})
        curr_time += timedelta(minutes=10)

    return timeline, tickets * TICKET_PRICE