from app.fifo.replay import FifoReplayError, ReplayResult


def test_replay_result_shape():
    r = ReplayResult("item", 2, 3, 1, 4)
    assert r.negative_movements == 2
    assert r.allocated_quantity == 3
    assert r.unresolved_quantity == 1
    assert r.affected_lots == 4


def test_replay_error_is_value_error():
    assert issubclass(FifoReplayError, ValueError)
