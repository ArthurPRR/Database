import json


class BTreeNode:

    def __init__(self, leaf=True):
        self.leaf = leaf
        self.keys = []
        self.offsets = []
        self.children = []

    def to_dict(self):
        return {
            "leaf": self.leaf,
            "keys": self.keys,
            "offsets": self.offsets,
            "children": [child.to_dict() for child in self.children]
        }

    @classmethod
    def from_dict(cls, data):
        node = cls(data["leaf"])
        node.keys = data["keys"]
        node.offsets = data["offsets"]
        node.children = [cls.from_dict(child) for child in data["children"]]
        return node


class BTree:

    def __init__(self, degree=64, root=None):
        if degree < 2:
            raise ValueError("B-Tree degree must be at least 2")
        self.degree = degree
        self.root = root if root is not None else BTreeNode()

    @staticmethod
    def _compare(a, b):
        return BTree._compare_values(json.loads(a), json.loads(b))

    @staticmethod
    def _compare_values(left, right):
        def kind(value):
            if value is None:
                return 0
            if isinstance(value, bool):
                return 1
            if isinstance(value, (int, float)):
                return 2
            if isinstance(value, str):
                return 3
            if isinstance(value, list):
                return 4
            if isinstance(value, dict):
                return 5
            return 6

        left_kind = kind(left)
        right_kind = kind(right)
        if left_kind != right_kind:
            return -1 if left_kind < right_kind else 1
        if left_kind == 0:
            return 0
        if left_kind in (1, 2, 3):
            return (left > right) - (left < right)
        if left_kind == 4:
            for left_item, right_item in zip(left, right):
                compared = BTree._compare_values(left_item, right_item)
                if compared:
                    return compared
            return (len(left) > len(right)) - (len(left) < len(right))

        left_items = sorted(left.items())
        right_items = sorted(right.items())
        for (left_key, left_value), (right_key, right_value) in zip(left_items, right_items):
            compared = (left_key > right_key) - (left_key < right_key)
            if compared:
                return compared
            compared = BTree._compare_values(left_value, right_value)
            if compared:
                return compared
        return (len(left_items) > len(right_items)) - (len(left_items) < len(right_items))

    def _lower_bound(self, node, key):
        low = 0
        high = len(node.keys)
        while low < high:
            middle = (low + high) // 2
            if self._compare(node.keys[middle], key) < 0:
                low = middle + 1
            else:
                high = middle
        return low

    def search(self, key):
        node = self.root
        while True:
            index = self._lower_bound(node, key)
            if index < len(node.keys) and self._compare(node.keys[index], key) == 0:
                return node.offsets[index]
            if node.leaf:
                return []
            node = node.children[index]

    def insert(self, key, offset):
        root = self.root
        if len(root.keys) == (2 * self.degree) - 1:
            new_root = BTreeNode(leaf=False)
            new_root.children.append(root)
            self.root = new_root
            self._split_child(new_root, 0)
            self._insert_non_full(new_root, key, offset)
        else:
            self._insert_non_full(root, key, offset)

    def _split_child(self, parent, index):
        child = parent.children[index]
        sibling = BTreeNode(child.leaf)
        middle = self.degree - 1

        median_key = child.keys[middle]
        median_offsets = child.offsets[middle]
        sibling.keys = child.keys[self.degree:]
        sibling.offsets = child.offsets[self.degree:]
        child.keys = child.keys[:middle]
        child.offsets = child.offsets[:middle]

        if not child.leaf:
            sibling.children = child.children[self.degree:]
            child.children = child.children[:self.degree]

        parent.keys.insert(index, median_key)
        parent.offsets.insert(index, median_offsets)
        parent.children.insert(index + 1, sibling)

    def _insert_non_full(self, node, key, offset):
        index = self._lower_bound(node, key)

        if node.leaf:
            if index < len(node.keys) and self._compare(node.keys[index], key) == 0:
                if offset not in node.offsets[index]:
                    node.offsets[index].append(offset)
            else:
                node.keys.insert(index, key)
                node.offsets.insert(index, [offset])
            return

        if index < len(node.keys) and self._compare(node.keys[index], key) == 0:
            if offset not in node.offsets[index]:
                node.offsets[index].append(offset)
            return

        if len(node.children[index].keys) == (2 * self.degree) - 1:
            self._split_child(node, index)
            if self._compare(node.keys[index], key) < 0:
                index += 1
            elif self._compare(node.keys[index], key) == 0:
                if offset not in node.offsets[index]:
                    node.offsets[index].append(offset)
                return

        self._insert_non_full(node.children[index], key, offset)

    def to_dict(self):
        return {
            "type": "btree",
            "degree": self.degree,
            "root": self.root.to_dict()
        }

    @classmethod
    def from_dict(cls, data):
        return cls(data["degree"], BTreeNode.from_dict(data["root"]))
