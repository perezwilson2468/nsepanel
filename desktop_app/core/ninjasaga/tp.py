from .leveling import ninjasaga_leveling


def tp_training(loop_times=None):
    return ninjasaga_leveling(loop_times=loop_times, training_mode="tp")
