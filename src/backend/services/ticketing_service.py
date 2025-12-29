from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

class TicketingService:
    def __init__(self):
        self.ticket_price = 3.5  # 3.5 RON is the basic price for a bus ticket in Cluj-Napoca
        self.ticket_validity = 45  # The validity of one ticket. In Cluj-Napoca one ticket is available for 45 minutes.
    
    def calculate_tickets(
        self, 
        total_duration_minutes: int, 
        start_time: datetime
    ) -> tuple[int, float]:
        """
        Calculate number of tickets needed and total cost.
        One ticket is valid for 45 minutes in Cluj-Napoca.
        """
        if total_duration_minutes <= 0:
            return 1, self.ticket_price
        
        # Calculate tickets needed
        tickets_needed = (total_duration_minutes + self.ticket_validity - 1) // self.ticket_validity
        tickets_needed = max(1, tickets_needed)
        
        total_cost = tickets_needed * self.ticket_price
        
        logger.info(f"Duration: {total_duration_minutes}min, Tickets: {tickets_needed}, Cost: {total_cost} RON")
        
        return tickets_needed, total_cost