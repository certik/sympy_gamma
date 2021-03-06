import pyjd # this is dummy in pyjs.
from pyjamas.ui.RootPanel import RootPanel
from pyjamas.ui.Label import Label
from pyjamas.ui.MouseListener import MouseHandler
from pyjamas.ui.HTML import HTML
from pyjamas.ui.FlowPanel import FlowPanel
from pyjamas.ui.SimplePanel import SimplePanel
from pyjamas.ui.TextArea import TextArea
from pyjamas.ui import KeyboardListener, Event
from pyjamas.HTTPRequest import HTTPRequest
from pyjamas import DOM

from pyjamas.JSONParser import JSONParser

import urllib

class InputArea(TextArea):

    def __init__(self, worksheet, cell_id, **kwargs):
        TextArea.__init__(self, **kwargs)
        self._worksheet = worksheet
        self._cell_id = cell_id
        self.addKeyboardListener(self)
        #self.addClickListener(self)
        self.addFocusListener(self)
        self.set_rows(1)
        self.setCharacterWidth(80)

    def onFocus(self, sender):
        self._worksheet.set_active_cell(self._cell_id)
        self._worksheet.get_active_cell().set_focus()

    def onBrowserEvent(self, event):
        event_type = DOM.eventGetType(event)
        if event_type == "blur":
            self._worksheet.get_active_cell().lost_focus()
        TextArea.onBrowserEvent(self, event)

    def rows(self):
        return self.getVisibleLines()

    def set_rows(self, rows):
        if rows == 0:
            rows = 1
        self.setVisibleLines(rows)

    def cols(self):
        return self.getCharacterWidth()

    def occupied_rows(self):
        text = self.getText()
        lines = text.split("\n")
        return len(lines)

    def set_cursor_coordinates(self, x, y):
        """
        Sets the cursor coordinates using the (x, y) tuple.
        """
        text = self.getText()
        lines = text.split("\n")
        i = 0
        for row, line in enumerate(lines):
            if row == y:
                break
            i += len(line) + 1  # we need to include "\n"
            if "\r" in line: # and also "\r"
                i -= 1
        pos = i + x
        if pos > len(text):
            pos = len(text)
        self.setCursorPos(pos)

    def cursor_coordinates(self):
        """
        Returns the cursor coordinates as a tuple (x, y).

        Example:

        >>> self.cursor_coordinates()
        (2, 3)
        """
        text = self.getText()
        lines = text.split("\n")
        pos = self.getCursorPos()
        if pos == 0:
            return (0, 0)
        i = 0
        cursor_row = -1
        cursor_col = -1
        for row, line in enumerate(lines):
            i += len(line) + 1  # we need to include "\n"
            if pos < i:
                cursor_row = row
                cursor_col = pos - i + len(line) + 1
                break
        return (cursor_col, cursor_row)

    def insert_at_cursor(self, inserted_text):
        pos = self.getCursorPos()
        text = self.getText()
        text = text[:pos] + inserted_text + text[pos:]
        self.setText(text)
        self.setCursorPos(pos+len(inserted_text))

    def update_size(self, enter_down=False, backspace_down=False):
        """
        Updates the size of the textarea to fit the text.

        This method is called from key down and key up events.

        enter_down ... if True, the enter is pressed, but not released
        backspace_down ... if True, the backspace is pressed but not released

        The enter_down/backspace_down arguments are used to predict the future
        size (since some browsers already move the cursors but don't adjust the
        size of the widget), so we need to do it ourselves.
        """
        x, y = self.cursor_coordinates()
        rows = self.occupied_rows()
        if enter_down:
            rows += 1
        if backspace_down:
            rows -= 1
        s = "row/col: (%s, %s), cursor pos: %d, %d, real_rows: %d, " \
                "enter down: %r, backspace down: %r" % \
                (self.rows(), self.cols(), x, y, rows, enter_down,
                        backspace_down)
        self.set_rows(rows)
        self._worksheet.print_info(s)

    def onKeyUp(self, sender, keyCode, modifiers):
        self.update_size()

    def onKeyDown(self, sender, key_code, modifiers):
        if key_code == KeyboardListener.KEY_TAB:
            self.insert_at_cursor("    ")
            event_preventDefault()
        elif key_code == KeyboardListener.KEY_BACKSPACE:
            x, y = self.cursor_coordinates()
            if (x == 0) and (y == 0):
                event_preventDefault()
                self._worksheet.join_cells()
            if (x == 0):
                self.update_size(backspace_down=True)
                return
            lines = self.getText().split("\n")
            line = lines[y]
            sline = line[:x]
            if sline.strip() == "" and len(sline) > 0:
                old_len = len(sline)
                new_len = int(old_len / 4) * 4
                if old_len == new_len:
                    new_len = new_len - 4
                lines[y] = sline[:new_len] + line[x:]
                pos = self.getCursorPos()
                self.setText("\n".join(lines))
                self.setCursorPos(pos - (old_len - new_len))
                event_preventDefault()
        elif key_code == KeyboardListener.KEY_ENTER and \
                modifiers == KeyboardListener.MODIFIER_SHIFT:
            event_preventDefault()
            self._worksheet.get_active_cell().evaluate()
            self._worksheet.move_to_next_cell(True)
        elif key_code == KeyboardListener.KEY_ENTER:
            self.update_size(enter_down=True)
        elif key_code == KeyboardListener.KEY_UP:
            x, y = self.cursor_coordinates()
            if y == 0:
                event_preventDefault()
                self._worksheet.move_to_prev_cell()
        elif key_code == KeyboardListener.KEY_DOWN:
            x, y = self.cursor_coordinates()
            if y + 1 == self.rows():
                event_preventDefault()
                self._worksheet.move_to_next_cell()

    def onKeyPress(self, sender, keyCode, modifiers):
        #print "on_key_press"
        pass

    def handle_eval_data(self, text):
        self._worksheet.show_output(self._cell_id, text)

class Loader:

    def __init__(self, cell):
        self._cell = cell

    def onCompletion(self, text):
        print "completed", text
        data = JSONParser().decode(text)
        self._cell.handle_eval_data(data["result"])
        print "ok"

    def onError(self, text, code):
        print "error", text, code

    def onTimeout(self, text):
        print "timeout", text

class InsertListener:

    def __init__(self, worksheet, id):
        self._worksheet = worksheet
        self._id = id

    def onClick(self, event):
        self._worksheet.insert_cell(self._id)

class EvaluateListener:

    def __init__(self, cell):
        self._cell = cell

    def onClick(self, event):
        event_preventDefault()
        self._cell.evaluate()
        self._cell._worksheet.move_to_next_cell(True)


class CellWidget(SimplePanel, MouseHandler):

    def __init__(self, worksheet, id):
        SimplePanel.__init__(self)
        MouseHandler.__init__(self)
        self._id = id
        self._worksheet = worksheet
        insert_new_cell = HTML("", StyleName="insert_new_cell")
        insert_new_cell.addClickListener(InsertListener(worksheet, self._id))
        input_prompt = HTML("In [%d]:" % self._id, Element=DOM.createSpan(),
                StyleName="input_prompt")
        cell_input = InputArea(worksheet, self._id, StyleName='cell_input')
        evaluate_button = HTML("evaluate", Element=DOM.createAnchor(),
                StyleName="eval_button", Visible=False)
        evaluate_button.getElement().setAttribute("href", "")
        evaluate_button.addClickListener(EvaluateListener(self))
        evaluate_button.addMouseListener(self)
        output_delimiter = HTML("", StyleName="output_delimiter")
        output_prompt = HTML("Out[%d]:" % self._id, Element=DOM.createSpan(),
                StyleName="output_prompt")
        cell_output = HTML("", Element=DOM.createSpan(),
                StyleName="cell_output")
        output_prompt.setVisible(False)
        p = FlowPanel(StyleName="cell")
        p.add(insert_new_cell)
        p.add(input_prompt)
        p.add(cell_input)
        p.add(evaluate_button)
        p.add(output_delimiter)
        p.add(output_prompt)
        p.add(cell_output)
        self.add(p)

        self._cell_input = cell_input
        self._cell_output = cell_output
        self._output_prompt = output_prompt
        self._evaluate_button = evaluate_button

        self._mouse_in = False

    def __repr__(self):
        return "<cell: %d>" % self._id

    def onMouseEnter(self, sender):
        self._mouse_in = True

    def onMouseLeave(self, sender):
        self._mouse_in = False

    def set_focus(self):
        """
        Focuses this cell.
        """
        self._cell_input.setFocus(True)
        self._evaluate_button.setVisible(True)

    def lost_focus(self, force=False):
        """
        Focus was lost.
        """
        if not self._mouse_in or force:
            self._evaluate_button.setVisible(False)

    def focus_prev_cell(self, prev):
        """
        Focuses the "prev" cell.

        Moves the cursor to the proper position.
        """
        x, y = self._cell_input.cursor_coordinates()
        y_new = prev._cell_input.rows() - 1
        prev._cell_input.set_cursor_coordinates(x, y_new)
        prev.set_focus()

    def focus_next_cell(self, next):
        """
        Focuses the "next" cell.

        Moves the cursor to the proper position.
        """
        x, y = self._cell_input.cursor_coordinates()
        y_new = 0
        next._cell_input.set_cursor_coordinates(x, y_new)
        next.set_focus()
        self.lost_focus(force=True)

    def join_with_prev(self, prev):
        """
        Joins this cell with the previous cell.

        It doesn't delete the current cell (this is the job of the Worksheet to
        properly delete ourselves).
        """
        if prev._cell_input.getText() == "":
            new_text = self._cell_input.getText()
        else:
            new_text = prev._cell_input.getText()
            if self._cell_input.getText() != "":
                new_text += "\n" + self._cell_input.getText()
        y_new = prev._cell_input.rows()
        if prev._cell_input.getText() == "":
            y_new -= 1
        prev._cell_input.setText(new_text)
        prev._cell_input.set_cursor_coordinates(0, y_new)
        prev.set_focus()

    def id(self):
        return self._id

    def evaluate(self):
        print "sending"
        payload = {"code": self._cell_input.getText(), "time": "ok"}
        payload = JSONParser().encode(payload)
        print "payload: %s" % payload
        data = urllib.urlencode({"payload": payload})
        HTTPRequest().asyncPost("/eval_cell/", data, Loader(self._cell_input))

class Worksheet:

    def __init__(self):
        self._echo = HTML()
        RootPanel().add(self._echo)
        self._echo2 = Label()
        RootPanel().add(self._echo2)
        self._i = 0
        self._active_cell = 0
        self._cell_list = []
        # cell id -> active index mapping:
        self._id2idx = {}
        self._other = []
        self.print_info("")

    def print_info(self, text):
        quiet = True
        if quiet:
            return
        self._echo.setHTML("Debugging Info: cells: %d, active cell: %d, " % \
                (self.num_cells(), self._active_cell) + text)
        self._echo2.setText("_cells_list: %r" % self._cell_list)

    def num_cells(self):
        return len(self._cell_list)

    def add_cell(self, insert_before_id=None):
        self._i += 1
        cell = CellWidget(self, self._i)
        if insert_before_id:
            idx = self._id2idx[insert_before_id]
            elem = self._cell_list[idx]
            before_idx = RootPanel().getWidgetIndex(elem)
            RootPanel().children.insert(before_idx, cell)
            RootPanel_insert_before(cell, elem.getElement())
            self._cell_list.insert(idx, cell)
            self.update_id2idx()
        else:
            RootPanel().add(cell)
            self._id2idx[self._i] = len(self._cell_list)
            self._cell_list.append(cell)
        self._other.append((cell._output_prompt, cell._cell_output))
        self.print_info("")

    def get_active_cell(self):
        return self._cell_list[self._active_cell]

    def set_active_cell(self, cell_id):
        self._active_cell = self._id2idx[cell_id]
        self.print_info("")

    def move_to_prev_cell(self):
        if self._active_cell > 0:
            current_cell = self._cell_list[self._active_cell]
            prev_cell = self._cell_list[self._active_cell-1]
            current_cell.focus_prev_cell(prev_cell)

    def move_to_next_cell(self, create=False):
        """
        Moves to the next cell.

        create .... if True, creates the next cell if we are at the end of the
        worksheet
        """
        if self._active_cell < self.num_cells()-1:
            current_cell = self._cell_list[self._active_cell]
            next_cell = self._cell_list[self._active_cell+1]
            current_cell.focus_next_cell(next_cell)
        elif create:
            self.add_cell()
            self.move_to_next_cell()
        elif self.num_cells() == 1:
            self._cell_list[0].set_focus()

    def insert_cell(self, id):
        self.add_cell(id)
        idx = self._id2idx[id]
        self._cell_list[idx-1].set_focus()

    def join_cells(self):
        current_cell = self._cell_list[self._active_cell]
        prev_cell = self._cell_list[self._active_cell-1]
        current_cell.join_with_prev(prev_cell)
        self.delete_cell(current_cell.id())

    def delete_cell(self, id):
        idx = self._id2idx[id]
        cell = self._cell_list[idx]
        self._cell_list = self._cell_list[:idx] + self._cell_list[idx+1:]
        cell.removeFromParent()
        self.update_id2idx()

    def update_id2idx(self):
        """
        Updates the cell id -> active index mapping.
        """
        self._id2idx = {}
        for n, cell in enumerate(self._cell_list):
            self._id2idx[cell.id()] = n

    def show_output(self, id, text):
        if text != "":
            prompt, cell = self._other[id-1]
            prompt.setVisible(True)
            cell.setHTML('<span class="cell_output">' + text + '</span>')

def getPrevSibling(elem):
    parent = DOM.getParent(elem)
    elem_index = DOM.getChildIndex(parent, elem)
    children = list(DOM.iterChildren(parent))
    return children[elem_index - 1]

def insertChildBefore(new_elem, elem):
    """
    Inserts an element "new_elem" before the element "elem".
    """
    parent = DOM.getParent(elem)
    id = DOM.getChildIndex(parent, elem)
    DOM.insertChild(parent, new_elem, id)

def RootPanel_insert_before(new_elem, elem):
    if elem is None:
        RootPanel().add(new_elem)
    else:
        parent = RootPanel()
        new_elem.setParent(parent)
        insertChildBefore(new_elem.getElement(), elem)

def event_preventDefault():
    """
    Prevents the current event's default behavior.
    """
    event = DOM.eventGetCurrentEvent()
    if event.preventDefault:
        event.preventDefault()
    else:
        event.returnValue = False

if __name__ == '__main__':
    pyjd.setup("templates/Hello.html")
    w = Worksheet()
    w.move_to_next_cell(True)
    pyjd.run()
