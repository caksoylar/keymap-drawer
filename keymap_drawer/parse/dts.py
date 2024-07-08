"""
Helper module to parse ZMK keymap-like DT syntax into a tree,
while keeping track of "compatible" values and utilities to parse
bindings fields.

The implementation is based on a nested expression parser for curly braces
through pyparsing with some additions on top to clean up comments and run the
C preprocessor using pcpp.
"""

import re
from collections import defaultdict
from io import StringIO
from itertools import chain

import pyparsing as pp
from pcpp.preprocessor import Action, OutputDirective, Preprocessor  # type: ignore


class DTNode:
    """Class representing a DT node with helper methods to extract fields."""

    name: str
    label: str | None
    content: str
    children: list["DTNode"]
    label_refs: dict[str, "DTNode"]

    def __init__(self, name: str, parse: pp.ParseResults):
        """
        Initialize a node from its name (which may be in the form of `label:name`)
        and `parse` which contains the node itself.
        """

        if ":" in name:
            self.label, self.name = name.split(":", maxsplit=1)
        else:
            self.label, self.name = None, name

        self.content = " ".join(elt for elt in parse if isinstance(elt, str))
        self.children = [
            DTNode(name=elt_p, parse=elt_n)
            for elt_p, elt_n in zip(parse[:-1], parse[1:])
            if isinstance(elt_p, str) and isinstance(elt_n, pp.ParseResults)
        ]

        # keep track of labeled nodes
        self.label_refs = {self.label: self} if self.label else {}
        for child in self.children:
            self.label_refs |= child.label_refs
            child.label_refs = {}

    def get_string(self, property_re: str) -> str | None:
        """Extract last defined value for a `string` type property matching the `property_re` regex."""
        out = None
        for m in re.finditer(rf'{property_re} = "(.*?)"', self.content):
            out = m.group(1)
        return out

    def get_array(self, property_re: str) -> list[str] | None:
        """Extract last defined values for a `array` type property matching the `property_re` regex."""
        matches = list(re.finditer(rf"{property_re} = (<.*?>( ?, ?<.*?>)*) ?;", self.content))
        if not matches:
            return None
        return list(chain.from_iterable(content.split(" ") for content in re.findall(r"<(.*?)>", matches[-1].group(1))))

    def get_phandle_array(self, property_re: str) -> list[str] | None:
        """Extract last defined values for a `phandle-array` type property matching the `property_re` regex."""
        if array_vals := self.get_array(property_re):
            return [
                f"&{stripped}"
                for binding in " ".join(array_vals).split("&")
                if (stripped := binding.strip().removeprefix("&"))
            ]
        return None

    def get_path(self, property_re: str) -> str | None:
        """
        Extract last defined value for a `path` type property matching the `property_re` regex.
        Only supports phandle paths `&p` rather than path types `"/a/b"` right now.
        """
        out = None
        for m in re.finditer(rf"{property_re} = &(.*?);", self.content):
            out = m.group(1)
        return out

    def __repr__(self):
        return (
            f"DTNode(name={self.name!r}, label={self.label!r}, content={self.content!r}, "
            f"children={[node.name for node in self.children]})\n"
        )


class DeviceTree:
    """
    Class that parses a DTS file (optionally preprocessed by the C preprocessor)
    and represents it as a DT tree, with some helpful methods.
    """

    _nodelabel_re = re.compile(r"([\w-]+) *: *([\w-]+) *{")
    _compatible_re = re.compile(r'compatible = "(.*?)"')
    _custom_data_header = "__keymap_drawer_data__"

    def __init__(  # pylint: disable=too-many-arguments
        self,
        in_str: str,
        file_name: str | None = None,
        preprocess: bool = True,
        preamble: str | None = None,
        additional_includes: list[str] | None = None,
    ):
        """
        Given an input DTS string `in_str` and `file_name` it is read from, parse it into an internap
        tree representation and track what "compatible" value each node has.

        If `preamble` is set to a non-empty string, prepend it to the read buffer.
        """
        self.raw_buffer = in_str
        self.file_name = file_name
        self.additional_includes = additional_includes
        if preamble:
            self.raw_buffer = preamble + "\n" + self.raw_buffer

        prepped = self._preprocess(self.raw_buffer, file_name, self.additional_includes) if preprocess else in_str

        # make sure node labels and names are glued together and comments are removed,
        # then parse with nested curly braces
        self.root = DTNode(
            "ROOT",
            pp.nested_expr("{", "};")
            .ignore("//" + pp.SkipTo(pp.lineEnd))
            .ignore(pp.c_style_comment)
            .parse_string("{ " + self._nodelabel_re.sub(r"\1:\2 {", prepped) + " };")[0],
        )

        # handle all node label-based overrides by appending their contents to the referred node's
        override_nodes = [node for node in self.root.children if node.name.startswith("&")]
        regular_nodes = [node for node in self.root.children if not node.name.startswith("&")]
        for node in override_nodes:
            if (label := node.name.removeprefix("&")) in self.root.label_refs:
                self.root.label_refs[label].content += " " + node.content
        self.root.children = regular_nodes

        # parse through all nodes and hash according to "compatible" values
        self.compatibles: defaultdict[str, list[DTNode]] = defaultdict(list)

        def assign_compatibles(node: DTNode) -> None:
            if m := self._compatible_re.search(node.content):
                self.compatibles[m.group(1)].append(node)
            for child in node.children:
                assign_compatibles(child)

        assign_compatibles(self.root)

        # find all chosen nodes and concatenate their content
        self.chosen = DTNode("__chosen__", pp.ParseResults())
        for root_child in self.root.children:
            for node in root_child.children:
                if node.name == "chosen":
                    self.chosen.content += " " + node.content

    @staticmethod
    def _preprocess(in_str: str, file_name: str | None = None, additional_includes: list[str] | None = None) -> str:
        def include_handler(*args):  # type: ignore
            raise OutputDirective(Action.IgnoreAndPassThrough)

        preprocessor = Preprocessor()
        preprocessor.line_directive = None
        preprocessor.on_include_not_found = include_handler
        preprocessor.assume_encoding = "utf-8"
        for path in additional_includes or []:
            preprocessor.add_path(path)
        preprocessor.parse(in_str, source=file_name)

        with StringIO() as f_out:
            preprocessor.write(f_out)
            prepped = f_out.getvalue()
        return re.sub(r"^\s*#.*?$", "", prepped)

    def get_compatible_nodes(self, compatible_value: str) -> list[DTNode]:
        """Return a list of nodes that have the given compatible value."""
        return self.compatibles[compatible_value]

    def get_chosen_property(self, property_name: str) -> str | None:
        """Return phandle for a given property in the /chosen node."""
        return self.chosen.get_path(re.escape(property_name))

    def preprocess_extra_data(self, data: str) -> str:
        """
        Given a string containing data, preprocess it in the same context as the
        original input buffer by appending the data to it and extracting the result
        afterwards.

        TODO(perf): Figure out a good interface to achieve this without running preprocessing
        twice.
        """
        in_str = self.raw_buffer + f"\n{self._custom_data_header}\n{data}"
        out = self._preprocess(in_str, self.file_name, self.additional_includes)
        data_pos = out.rfind(f"\n{self._custom_data_header}\n")
        assert data_pos >= 0, (
            f"Preprocessing extra data failed, please make sure '{self._custom_data_header}' "
            "does not get modified by #define's"
        )
        return out[data_pos + len(self._custom_data_header) + 2 :]

    def __repr__(self):
        def recursive_repr(node):
            return repr(node) + "".join(recursive_repr(child) for child in node.children)

        return recursive_repr(self.root)
