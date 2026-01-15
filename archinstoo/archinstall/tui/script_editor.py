import curses

from .curses_menu import Tui
from .types import STYLE, Chars


class ScriptEditor:
	"""A simple multi-line text editor for custom scripts."""

	def __init__(
		self,
		title: str = 'Script Editor',
		preset: str = '',
	):
		self._title = title
		self._lines: list[str] = preset.split('\n') if preset else ['']
		self._cursor_y = 0
		self._cursor_x = 0
		self._scroll_y = 0
		self._running = True
		self._saved = False

	def edit(self) -> str | None:
		"""Open the editor and return the script content, or None"""
		screen = Tui.t().screen
		curses.curs_set(1)
		screen.keypad(True)

		try:
			while self._running:
				self._draw(screen)
				key = screen.getch()
				self._handle_key(key)
		finally:
			curses.curs_set(0)

		if self._saved:
			return '\n'.join(self._lines)
		return None

	def _draw(self, screen: curses.window) -> None:
		screen.erase()
		max_y, max_x = screen.getmaxyx()
		tui = Tui.t()
		normal = tui.get_color(STYLE.NORMAL)
		highlight = tui.get_color(STYLE.CURSOR_STYLE)

		# Header
		header = f' {self._title} '
		screen.addstr(0, 0, Chars.Horizontal * max_x, normal)
		screen.addstr(0, 2, header, highlight)

		# Calculate visible area
		edit_start_y = 1
		edit_end_y = max_y - 3
		visible_lines = edit_end_y - edit_start_y

		# Adjust scroll to keep cursor visible
		if self._cursor_y < self._scroll_y:
			self._scroll_y = self._cursor_y
		elif self._cursor_y >= self._scroll_y + visible_lines:
			self._scroll_y = self._cursor_y - visible_lines + 1

		# Draw lines with line numbers
		line_num_width = max(3, len(str(len(self._lines)))) + 1

		for i in range(visible_lines):
			line_idx = self._scroll_y + i
			y_pos = edit_start_y + i

			if line_idx < len(self._lines):
				# Line number
				line_num = f'{line_idx + 1:>{line_num_width - 1}} '
				screen.addstr(y_pos, 0, line_num, normal)

				# Line content
				line = self._lines[line_idx]
				available_width = max_x - line_num_width - 1
				display_line = line[:available_width]
				screen.addstr(y_pos, line_num_width, display_line, normal)
			else:
				# Empty line indicator
				screen.addstr(y_pos, line_num_width - 2, '~', normal)

		# Status bar
		status_y = max_y - 2
		screen.addstr(status_y, 0, Chars.Horizontal * max_x, normal)

		pos_info = f'Ln {self._cursor_y + 1}, Col {self._cursor_x + 1}'
		help_text = 'F2:save  F10/Esc:cancel'
		screen.addstr(status_y + 1, 0, help_text, normal)
		screen.addstr(status_y + 1, max_x - len(pos_info) - 1, pos_info, normal)

		# Position cursor
		cursor_screen_y = edit_start_y + (self._cursor_y - self._scroll_y)
		cursor_screen_x = line_num_width + min(self._cursor_x, max_x - line_num_width - 1)
		try:
			screen.move(cursor_screen_y, cursor_screen_x)
		except curses.error:
			pass

		screen.refresh()

	def _handle_key(self, key: int) -> None:
		current_line = self._lines[self._cursor_y]

		if key in (27, curses.KEY_F10):  # ESC or F10 - cancel
			self._running = False
		elif key == curses.KEY_F2:  # F2 - save
			self._saved = True
			self._running = False
		elif key == curses.KEY_UP:
			if self._cursor_y > 0:
				self._cursor_y -= 1
				self._clamp_cursor_x()
		elif key == curses.KEY_DOWN:
			if self._cursor_y < len(self._lines) - 1:
				self._cursor_y += 1
				self._clamp_cursor_x()
		elif key == curses.KEY_LEFT:
			if self._cursor_x > 0:
				self._cursor_x -= 1
			elif self._cursor_y > 0:
				self._cursor_y -= 1
				self._cursor_x = len(self._lines[self._cursor_y])
		elif key == curses.KEY_RIGHT:
			if self._cursor_x < len(current_line):
				self._cursor_x += 1
			elif self._cursor_y < len(self._lines) - 1:
				self._cursor_y += 1
				self._cursor_x = 0
		elif key == curses.KEY_HOME:
			self._cursor_x = 0
		elif key == curses.KEY_END:
			self._cursor_x = len(current_line)
		elif key in (curses.KEY_BACKSPACE, 127, 8):  # Backspace
			if self._cursor_x > 0:
				self._lines[self._cursor_y] = current_line[: self._cursor_x - 1] + current_line[self._cursor_x :]
				self._cursor_x -= 1
			elif self._cursor_y > 0:
				# Join with previous line
				prev_len = len(self._lines[self._cursor_y - 1])
				self._lines[self._cursor_y - 1] += current_line
				self._lines.pop(self._cursor_y)
				self._cursor_y -= 1
				self._cursor_x = prev_len
		elif key == curses.KEY_DC:  # Delete key
			if self._cursor_x < len(current_line):
				self._lines[self._cursor_y] = current_line[: self._cursor_x] + current_line[self._cursor_x + 1 :]
			elif self._cursor_y < len(self._lines) - 1:
				# Join with next line
				self._lines[self._cursor_y] += self._lines[self._cursor_y + 1]
				self._lines.pop(self._cursor_y + 1)
		elif key in (curses.KEY_ENTER, 10, 13):  # Enter
			# Split line
			before = current_line[: self._cursor_x]
			after = current_line[self._cursor_x :]
			self._lines[self._cursor_y] = before
			self._cursor_y += 1
			self._lines.insert(self._cursor_y, after)
			self._cursor_x = 0
		elif key == 9:  # Tab
			self._lines[self._cursor_y] = current_line[: self._cursor_x] + '\t' + current_line[self._cursor_x :]
			self._cursor_x += 1
		elif 32 <= key <= 126:  # Printable ASCII
			self._lines[self._cursor_y] = current_line[: self._cursor_x] + chr(key) + current_line[self._cursor_x :]
			self._cursor_x += 1

	def _clamp_cursor_x(self) -> None:
		max_x = len(self._lines[self._cursor_y])
		self._cursor_x = max(0, min(self._cursor_x, max_x))


def edit_script(preset: str = '', title: str = 'Custom Commands') -> str | None:
	editor = ScriptEditor(title=title, preset=preset)
	return editor.edit()
