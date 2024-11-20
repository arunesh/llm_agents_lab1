from typing import Dict, List
from typing import Annotated, Literal
from autogen import ConversableAgent
import sys
import os, math, re


restaurant_datafile="restaurant-data.txt"
restaurant_name_str = ""

# Sequence patterns: https://microsoft.github.io/autogen/0.2/docs/tutorial/conversation-patterns
REVIEWANALYSIS_AGENT_PROMPT = """
You are an helpful AI Assistant, with the ability to analyze and rate (from 1 to 5) the food service and customer service at a restaurant given the reviews.
Use the following table:
Score 1/5 has one of these adjectives: awful, horrible, or disgusting.
Score 2/5 has one of these adjectives: bad, unpleasant, or offensive.
Score 3/5 has one of these adjectives: average, uninspiring, or forgettable.
Score 4/5 has one of these adjectives: good, enjoyable, or satisfying.
Score 5/5 has one of these adjectives: awesome, incredible, or amazing.
Given a list of individual reviews, use the above table to output a rating as an integer along with the review. Output one integer each separately for food service and one for
customer service. Provide your output as a list of tuples (x,y, z) where x is the food service rating and y is the customer service rating for the review z.
"""

ENTRYPOINT_AGENT_PROMPT = """
You are an helpful AI Assistant, with the ability to fetch restaurants and answer questions based on provided restaurant
reviews. Use the tool calling to fetch reviews for a given restaurant requested by the user.
When the reviews are given as a list, copy them to the output for the next AI assistant to work on. Do not summarize.
"""

def normalize_restaurant_name(name):
    n = name.replace("-", " ")
    return n.strip().lower()

def get_substring_between(text, start_char, end_char):
    start_index = text.find(start_char)
    end_index = text.find(end_char, start_index + 1)

    # Check if both characters are found
    if start_index != -1 and end_index != -1:
        return text[start_index + 1: end_index ]
    else:
        return text  #just return the orignal text if [] are absent.

def score_summary_method(sender: ConversableAgent, recipient: ConversableAgent, summary_args: dict):
    msg = recipient.last_message(sender)["content"]
    get_substring_between(msg, "[", "]")
    return "*************** Summary Method called:" + recipient.last_message(sender)["content"]

def extract_score(t):
    splits = t.replace("(", "").replace(")", "").split(",")
    f = int(splits[0])
    c = int(splits[1])
    return f, c
    
def compute_final_score(last_msg):
    global restaurant_name_str
    msg1 = get_substring_between(last_msg, "[", "]")
    res = re.findall(r'\(.*?\)', msg1)

    food_scores=[]
    service_scores = []
    for t in res:
        (f, c) = extract_score(t)
        food_scores.append(f)
        service_scores.append(c)
    return calculate_overall_score(restaurant_name_str, food_scores, service_scores)

def load_restaurant_reviews() -> Dict[str, List[str]]:
    restaurant_map :Dict[str, List[str]] = {}
    with open(restaurant_datafile) as file:
        for line in file:
            # print(line)
            splits = line.split(".")
             # Use setdefault to ensure the key has a list, then append the value
            restaurant_map.setdefault(normalize_restaurant_name(splits[0]), []).append('.'.join(splits[1:]))
    # Iterate through the dictionary
    # for key, value in restaurant_map.items():
    #    print(f"Key: {key}, Value: {value}")
    return restaurant_map

def fetch_restaurant_data(restaurant_name:  Annotated[str, "restaurant name"]) -> Dict[str, List[str]]:
    global restaurant_name_str
  
    # This function takes in a restaurant name and returns the reviews for that restaurant. 
    # The output should be a dictionary with the key being the restaurant name and the value being a list of reviews for that restaurant.
    # The "data fetch agent" should have access to this function signature, and it should be able to suggest this as a function call. 
    # Example:
    # > fetch_restaurant_data("Applebee's")
    # {"Applebee's": ["The food at Applebee's was average, with nothing particularly standing out.", ...]}
    restaurant_name_str = restaurant_name
    name = normalize_restaurant_name(restaurant_name)
    reviews = load_restaurant_reviews()
    return {restaurant_name: reviews[name]}


def calculate_overall_score(restaurant_name: str, food_scores: List[int], customer_service_scores: List[int]) -> Dict[str, float]:
    # TODO
    # This function takes in a restaurant name, a list of food scores from 1-5, and a list of customer service scores from 1-5
    # The output should be a score between 0 and 10, which is computed as the following:
    # SUM(sqrt(food_scores[i]**2 * customer_service_scores[i]) * 1/(N * sqrt(125)) * 10
    # The above formula is a geometric mean of the scores, which penalizes food quality more than customer service. 
    # Example:
    # > calculate_overall_score("Applebee's", [1, 2, 3, 4, 5], [1, 2, 3, 4, 5])
    # {"Applebee's": 5.048}
    # NOTE: be sure to that the score includes AT LEAST 3  decimal places. The public tests will only read scores that have 
    # at least 3 decimal places.
    N = len(food_scores)
    if (N != len(customer_service_scores)):
        raise ValueError("Both food_scores and customer_service_scores must have equal length.")
    sum:float = 0.0
    for (f, c) in zip(food_scores, customer_service_scores):
        t = math.sqrt(f*f*c/125.0)
        sum = sum + t
        # print(f"Local score: {f}, {c}, {t}")
    #print(f"sum = {sum}, N = {N}")
    sum = sum / float(N)
    sum = 10.0 * sum
    print(f"Review for restaurant {restaurant_name} = {sum}")
    return "{\""+ restaurant_name + "\": "+ f"{sum:.3f}" + "}"

def get_data_fetch_agent_prompt(restaurant_query: str) -> str:
    # TODO
    # It may help to organize messages/prompts within a function which returns a string. 
    # For example, you could use this function to return a prompt for the data fetch agent 
    # to use to fetch reviews for a specific restaurant.
    pass

# TODO: feel free to write as many additional functions as you'd like.

# Do not modify the signature of the "main" function.
def main(user_query: str):
    restaurant_review_agent = ConversableAgent("Restaurant Review agent", system_message=ENTRYPOINT_AGENT_PROMPT, 
        llm_config={"config_list": [{"model": "gpt-4", "temperature": 0.9, "api_key": os.environ.get("OPENAI_API_KEY")}]},
        human_input_mode="NEVER",)  # Never ask for human input.


    # The user proxy agent is used for interacting with the assistant agent
    # and executes tool calls.
    user_proxy = ConversableAgent(
        name="User",
        llm_config=False,
        is_termination_msg=lambda msg: msg.get("content") is not None and "TERMINATE" in msg["content"],
        human_input_mode="NEVER",)

    # Tool use: https://microsoft.github.io/autogen/0.2/docs/tutorial/tool-use/
    # Register the tool signature with the assistant agent.
    restaurant_review_agent.register_for_llm(name="fetch_restaurant_reviews",
                                         description="Fetch reviews for a given restaurant name.")(fetch_restaurant_data)

    # Register the tool function with the user proxy agent.
    user_proxy.register_for_execution(name="fetch_restaurant_reviews")(fetch_restaurant_data)

    review_analysis_agent = ConversableAgent("Review Analysis agent", system_message=REVIEWANALYSIS_AGENT_PROMPT, 
            llm_config={"config_list": [{"model": "gpt-4", "temperature": 0.9, "api_key": os.environ.get("OPENAI_API_KEY")}]},
            human_input_mode="NEVER",)  # Never ask for human input.

    chat_result = user_proxy.initiate_chats([
        {
            "recipient": restaurant_review_agent,
            "message": user_query,
            "max_turns": 2,
            "summary_method": "last_msg",
        },
        {
            "recipient": review_analysis_agent,
            "message": "Given these reviews, generate separate scores for the food and customer service.",
            "max_turns": 1,
            "summary_method": "last_msg",
        },])

    s = compute_final_score(chat_result[-1].summary)
    print(s)
    # TODO
    # Create more agents here. 
    
    # TODO
    # Fill in the argument to `initiate_chats` below, calling the correct agents sequentially.
    # If you decide to use another conversation pattern, feel free to disregard this code.
    
    # Uncomment once you initiate the chat with at least one agent.
    # result = entrypoint_agent.initiate_chats([{}])
    
# DO NOT modify this code below.
if __name__ == "__main__":
    assert len(sys.argv) > 1, "Please ensure you include a query for some restaurant when executing main."
    main(sys.argv[1])