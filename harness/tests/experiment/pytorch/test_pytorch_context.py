import pytest
import torch
import pathlib

import determined as det
from typing import Any, Dict
from _pytest import monkeypatch

from determined import errors, pytorch, tensorboard



class TestPyTorchContext:
    def setup_method(self) -> None:
        self.config = {"hyperparameters": {"global_batch_size": 4, "dataloader_type": "determined"}}
        core_context, env = det._make_local_execution_env(
            managed_training=False,
            test_mode=False,
            config=self.config,
            checkpoint_dir="/tmp",
            limit_gpus=1,
        )

        context = pytorch.PyTorchTrialContext(
            core_context=core_context,
            trial_seed=env.trial_seed,
            hparams=self.config["hyperparameters"],
            slots_per_trial=1,
            num_gpus=1,
            exp_conf=self.config,
            aggregation_frequency=1,
            steps_completed=0,
            managed_training=False,
            debug_enabled=False,
        )

        context._set_default_gradient_compression(False)
        context._set_default_average_aggregated_gradients(True)

        assert isinstance(context, pytorch.PyTorchTrialContext)
        self.context = context

    def test_average_gradients(self) -> None:
        assert self.context._average_gradients(None, 1) is None

    def test_training_not_started(self) -> None:
        with pytest.raises(errors.InternalException):
            self.context.is_epoch_start()
        with pytest.raises(errors.InternalException):
            self.context.is_epoch_end()
        with pytest.raises(errors.InternalException):
            self.context.current_train_batch()
        with pytest.raises(errors.InternalException):
            self.context.current_train_epoch()
        self.context._managed_training = True
        with pytest.raises(errors.InternalException):
            self.context._should_communicate_and_update()

    def test_wrap_scaler(self) -> None:
        scaler = torch.cuda.amp.GradScaler()  # type: ignore # GradScaler.__init__ is untyped
        assert scaler == self.context.wrap_scaler(scaler)
        assert scaler == self.context._scaler

    def test_context_method(
        self, monkeypatch: monkeypatch.MonkeyPatch, tmp_path: pathlib.Path
    ) -> None:
        def mock_get_base_path(dummy: Dict[str, Any]) -> pathlib.Path:
            return tmp_path

        monkeypatch.setattr(tensorboard, "get_base_path", mock_get_base_path)

        assert self.context.tbd_writer is None
        files = list(tmp_path.iterdir())
        assert len(files) == 0

        with self.context.get_tensorboard_writer() as writer:
            writer.add_scalar("foo", 7, 0)
            writer.add_scalar("foo", 8, 1)

        with self.context.get_tensorboard_writer() as writer:
            writer.add_scalar("foo", 9, 2)
            writer.add_scalar("foo", 10, 3)
            writer.add_scalar("foo", 11, 4)

        files = list(tmp_path.iterdir())
        assert len(files) == 2
