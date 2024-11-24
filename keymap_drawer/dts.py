"""
Helper module to parse ZMK keymap-like DT syntax to extract nodes with
given "compatible" values, and utilities to extract their properties and
child nodes.

The implementation is based on pcpp to run the C preprocessor, and then
tree-sitter-devicetree to run queries to find compatible nodes and extract properties.
Node overrides via node references are supported in a limited capacity.
"""

import logging
import re
from io import StringIO
from itertools import chain

import tree_sitter_devicetree as ts
from pcpp.preprocessor import Action, OutputDirective, Preprocessor  # type: ignore
from tree_sitter import Language, Node, Parser, Tree

logger = logging.getLogger(__name__)

TS_LANG = Language(ts.language())


class DTNode:
    """Class representing a DT node with helper methods to extract fields."""

    name: str
    label: str | None
    content: str
    children: list["DTNode"]

    def __init__(self, node: Node, text_buf: bytes, override_nodes: list["DTNode"] | None = None):
        """
        Initialize a node from its name (which may be in the form of `label:name`)
        and `parse` which contains the node itself.
        """
        self.node = node
        self.text_buf = text_buf
        name_node = node.child_by_field_name("name")
        assert name_node is not None
        self.name = self._get_content(name_node)
        self.label = self._get_content(v) if (v := node.child_by_field_name("label")) is not None else None
        self.children = sorted(
            (DTNode(child, text_buf, override_nodes) for child in node.children if child.type == "node"),
            key=lambda x: x.node.start_byte,
        )
        self.overrides = []
        if override_nodes and self.label is not None:
            # consider pre-compiling nodes by label for performance
            self.overrides = [node for node in override_nodes if self.label == node.name.lstrip("&")]

    def _get_content(self, node: Node) -> str:
        return self.text_buf[node.start_byte : node.end_byte].decode("utf-8").replace("\n", " ")

    def _get_property(self, property_re: str) -> list[Node] | None:
        children = [node for node in self.node.children if node.type == "property"]
        for override_node in self.overrides:
            children += [node for node in override_node.node.children if node.type == "property"]
        for child in children[::-1]:
            name_node = child.child_by_field_name("name")
            assert name_node is not None
            if re.match(property_re, self._get_content(name_node)):
                return child.children_by_field_name("value")
        return None

    def get_string(self, property_re: str) -> str | None:
        """Extract last defined value for a `string` type property matching the `property_re` regex."""
        if (nodes := self._get_property(property_re)) is None:
            return None
        return self._get_content(nodes[0]).strip('"')

    def get_array(self, property_re: str) -> list[str] | None:
        """Extract last defined values for a `array` type property matching the `property_re` regex."""
        if (nodes := self._get_property(property_re)) is None:
            return None
        return list(
            chain.from_iterable(
                self._get_content(node).strip("<>").split() for node in nodes if node.type == "integer_cells"
            )
        )

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
        if (nodes := self._get_property(property_re)) is None:
            return None
        return self._get_content(nodes[0]).lstrip("&")

    def __repr__(self) -> str:
        content = " ".join(self._get_content(node) for node in self.node.children if node.type != "node")
        return (
            f"DTNode(name={self.name!r}, label={self.label!r}, content={content!r}, "
            f"children={[node.name for node in self.children]})"
        )


class DeviceTree:
    """
    Class that parses a DTS file (optionally preprocessed by the C preprocessor)
    and provides methods to extract `compatible` and `chosen` nodes as DTNode's.
    """

    _custom_data_header = "__keymap_drawer_data__"

    def __init__(
        self,
        in_str: str,
        file_name: str | None = None,
        preprocess: bool = True,
        preamble: str | None = None,
        additional_includes: list[str] | None = None,
    ):
        """
        Given an input DTS string `in_str` and `file_name` it is read from, parse it to be
        able to get `compatible` and `chosen` nodes.
        For performance reasons, the whole tree isn't parsed into DTNode's.

        If `preamble` is set to a non-empty string, prepend it to the read buffer.
        """
        self.raw_buffer = in_str
        self.file_name = file_name
        self.additional_includes = additional_includes
        if preamble:
            self.raw_buffer = preamble + "\n" + self.raw_buffer

        prepped = self._preprocess(self.raw_buffer, file_name, self.additional_includes) if preprocess else in_str

        self.ts_buffer = prepped.encode("utf-8")
        tree = Parser(TS_LANG).parse(self.ts_buffer)
        self.root_nodes = self._find_root_ts_nodes(tree)
        self.override_nodes = [DTNode(node, self.ts_buffer) for node in self._find_override_ts_nodes(tree)]
        self.chosen_nodes = [DTNode(node, self.ts_buffer) for node in self._find_chosen_ts_nodes(tree)]

    @staticmethod
    def _find_root_ts_nodes(tree: Tree) -> list[Node]:
        return sorted(
            TS_LANG.query(
                """
                (document
                  (node
                    name: (identifier) @nodename
                    (#eq? @nodename "/")
                  ) @rootnode
                )
                """
            )
            .captures(tree.root_node)
            .get("rootnode", []),
            key=lambda node: node.start_byte,
        )

    @staticmethod
    def _find_override_ts_nodes(tree: Tree) -> list[Node]:
        return sorted(
            TS_LANG.query(
                """
                (document
                  (node
                    name: (reference
                      label: (identifier)
                    )
                  ) @overridenode
                )
                """
            )
            .captures(tree.root_node)
            .get("overridenode", []),
            key=lambda node: node.start_byte,
        )

    @staticmethod
    def _find_chosen_ts_nodes(tree: Tree) -> list[Node]:
        return sorted(
            TS_LANG.query(
                """
                (node
                  name: (identifier) @nodename
                  (#eq? @nodename "chosen")
                ) @chosennode
                """
            )
            .set_max_start_depth(2)
            .captures(tree.root_node)
            .get("chosennode", []),
            key=lambda node: node.start_byte,
        )

    @staticmethod
    def _preprocess(in_str: str, file_name: str | None = None, additional_includes: list[str] | None = None) -> str:
        # ignore__has_include(...) in preprocessor ifs because pcpp can't handle them
        in_str = re.sub(r"__has_include\(.*?\)", "0", in_str)

        def include_handler(*args):  # type: ignore
            raise OutputDirective(Action.IgnoreAndPassThrough)

        def on_error_handler(file, line, msg):  # type: ignore
            logger.warning("preprocessor: %s:%d error: %s", file, line, msg)

        preprocessor = Preprocessor()
        preprocessor.line_directive = None
        preprocessor.on_include_not_found = include_handler
        preprocessor.on_error = on_error_handler
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
        query = TS_LANG.query(
            rf"""
            (node
              (property name: (identifier) @prop value: (string_literal) @propval)
              (#eq? @prop "compatible") (#eq? @propval "\"{compatible_value}\"")
            ) @node
            """
        )
        nodes = chain.from_iterable(query.captures(node).get("node", []) for node in self.root_nodes)
        return sorted(
            (DTNode(node, self.ts_buffer, self.override_nodes) for node in nodes), key=lambda x: x.node.start_byte
        )

    def get_chosen_property(self, property_name: str) -> str | None:
        """Return phandle for a given property in the /chosen node."""
        phandle = None
        for node in self.chosen_nodes:
            if (val := node.get_path(re.escape(property_name))) is not None:
                phandle = val
        return phandle

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
