"""Tests for progress indicator utilities."""

from src.utils.progress import create_progress, create_spinner_progress


class TestCreateProgress:
    """Tests for create_progress context manager."""

    def test_create_progress_as_context_manager(self):
        """Test create_progress can be used as context manager."""
        with create_progress() as progress:
            assert progress is not None

    def test_create_progress_has_add_task(self):
        """Test progress has add_task method."""
        with create_progress() as progress:
            assert hasattr(progress, "add_task")

    def test_create_progress_can_add_task(self):
        """Test progress can add and track tasks."""
        with create_progress() as progress:
            task_id = progress.add_task("Testing", total=100)
            assert task_id is not None

    def test_create_progress_can_update_task(self):
        """Test progress can update task progress."""
        with create_progress() as progress:
            task_id = progress.add_task("Testing", total=100)
            progress.update(task_id, advance=50)
            # Should not raise


class TestCreateSpinnerProgress:
    """Tests for create_spinner_progress function."""

    def test_create_spinner_progress_returns_progress(self):
        """Test create_spinner_progress returns a Progress instance."""
        progress = create_spinner_progress()
        assert progress is not None

    def test_create_spinner_progress_has_add_task(self):
        """Test spinner progress has add_task method."""
        progress = create_spinner_progress()
        assert hasattr(progress, "add_task")

    def test_create_spinner_progress_has_start_stop(self):
        """Test spinner progress has start and stop methods."""
        progress = create_spinner_progress()
        assert hasattr(progress, "start")
        assert hasattr(progress, "stop")

    def test_create_spinner_progress_can_be_used(self):
        """Test spinner progress can be started and stopped."""
        progress = create_spinner_progress()
        progress.start()
        task_id = progress.add_task("Spinning...")
        progress.update(task_id, description="Done!")
        progress.stop()
        # Should complete without error
