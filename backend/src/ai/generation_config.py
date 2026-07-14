GENERATION_CONFIG = {
    "quick": {
        "num_predict": 100,
        "temperature": 0.2,
        "top_p": 0.9,
    },
    "learn": {
        "num_predict": 220,
        "temperature": 0.3,
        "top_p": 0.9,
    },
    "revision": {
        "num_predict": 160,
        "temperature": 0.2,
        "top_p": 0.9,
    },
    "prelims": {
        "num_predict": 180,
        "temperature": 0.2,
        "top_p": 0.9,
    },
    "mains": {
        "num_predict": 450,
        "temperature": 0.4,
        "top_p": 0.9,
    },
    "interview": {
        "num_predict": 320,
        "temperature": 0.5,
        "top_p": 0.95,
    },
}


DEPTH_LIMITS = {"quick": 300, "standard": 650, "detailed": 1100}


def get_generation_config(mode, depth="standard"):
    config = dict(GENERATION_CONFIG.get(mode, GENERATION_CONFIG["learn"]))
    config["num_predict"] = DEPTH_LIMITS.get(depth, DEPTH_LIMITS["standard"])
    return config
