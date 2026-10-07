from langgraph.store.base import BaseStore
from src.schemas.UserProfile import UserProfile


NAMESPACE_PREFIX="memory_profile"
KEY="user_memory"

def _namespace(customer_id: int) -> tuple[str, str]:
    """One namespace per customer; namespace parts must be strings."""
    return (NAMESPACE_PREFIX, str(customer_id))

def load_profile(store:BaseStore,customer_id:int) -> UserProfile|None:
    """Return the customer's saved profile, or None if nothing is saved."""
    item=store.get((_namespace(customer_id)),KEY)
    return UserProfile(**item.value) if item else None
    
def save_profile(store:BaseStore,profile:UserProfile)->None:
    """Write the profile under its customer's namespace."""
    store.put(_namespace(profile.customer_id), KEY, profile.model_dump())
   
    
    


    
