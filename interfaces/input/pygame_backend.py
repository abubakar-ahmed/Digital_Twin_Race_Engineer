"""pygame joystick (preferred) or keyboard fallback for DIL."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from interfaces.input.raw_types import RawInput


class InputPollable(Protocol):
    def read_raw(self) -> RawInput:
        ...


@dataclass(slots=True)
class JoystickAxisMap:
    """Per-wheel mapping; print once and adjust to your hardware."""

    steering: int = 0
    throttle: int = 1
    brake: int = 2


class PygameJoystickBackend:
    def __init__(
        self,
        device_index: int = 0,
        axis_map: JoystickAxisMap | None = None,
        *,
        print_calibration: bool = True,
    ) -> None:
        import pygame

        self._pygame = pygame
        if not pygame.get_init():
            pygame.init()
        pygame.joystick.init()
        if pygame.joystick.get_count() == 0:
            raise RuntimeError("No joystick detected — plug in a wheel or use keyboard backend.")
        self._joy = pygame.joystick.Joystick(device_index)
        self._joy.init()
        self._map = axis_map or JoystickAxisMap()
        if print_calibration:
            pygame.event.pump()
            st = self._joy.get_axis(self._map.steering)
            th = self._joy.get_axis(self._map.throttle)
            br = self._joy.get_axis(self._map.brake)
            print(f"[DIL] Raw axes (steer, throttle, brake) = ({st:.3f}, {th:.3f}, {br:.3f}) — verify mapping/invert in JoystickAxisMap / InputProcessor.")

    def read_raw(self) -> RawInput:
        self._pygame.event.pump()
        j = self._joy
        m = self._map
        return RawInput(
            steering_axis=float(j.get_axis(m.steering)),
            throttle=float(j.get_axis(m.throttle)),
            brake=float(j.get_axis(m.brake)),
            pedals_are_axes=True,
        )


class PygameKeyboardBackend:
    def __init__(self) -> None:
        import pygame

        self._pygame = pygame
        if not pygame.get_init():
            pygame.init()
        if pygame.display.get_surface() is None:
            try:
                pygame.display.set_mode((320, 200))
            except pygame.error:
                # Headless: caller should use scripted read_raw or set SDL_VIDEODRIVER=dummy before pygame import.
                pass

    def read_raw(self) -> RawInput:
        pygame = self._pygame
        pygame.event.pump()
        keys = pygame.key.get_pressed()
        throttle = 1.0 if keys[pygame.K_w] else 0.0
        brake = 1.0 if keys[pygame.K_s] else 0.0
        if keys[pygame.K_a]:
            steering = -1.0
        elif keys[pygame.K_d]:
            steering = 1.0
        else:
            steering = 0.0
        return RawInput(
            steering_axis=steering,
            throttle=throttle,
            brake=brake,
            pedals_are_axes=False,
        )


def create_pygame_backend(*, prefer_joystick: bool = True) -> InputPollable:
    """Joystick if present, else keyboard (may open a small pygame window for keys)."""
    import pygame

    if not pygame.get_init():
        pygame.init()
    pygame.joystick.init()
    if prefer_joystick and pygame.joystick.get_count() > 0:
        return PygameJoystickBackend(print_calibration=True)
    return PygameKeyboardBackend()
