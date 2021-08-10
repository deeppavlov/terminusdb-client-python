import ast
from copy import copy, deepcopy
from enum import Enum, EnumMeta
from hashlib import sha256
from typing import Optional, Union
from urllib.parse import quote
from uuid import uuid4

from numpydoc.docscrape import ClassDoc
from typeguard import check_type

from .. import woql_type as wt
from ..woql_type import CONVERT_TYPE
from ..woqlclient.woqlClient import WOQLClient

# from typeguard import check_type


class TerminusKey(type):
    pass


class HashKey(metaclass=TerminusKey):
    """Generating ID with SHA256 using provided keys"""

    at_type = "Hash"

    def __init__(self, keys: Union[str, list]):
        self._keys = keys

    def idgen(self, obj: Union["DocumentTemplate", dict]):
        key_list = []
        for item in self._keys:
            if hasattr(obj, item):
                key_item = ast.literal_eval(f"obj.{item}")
            elif isinstance(obj, dict) and obj.get(item) is not None:
                key_item = obj.get(item)
            else:
                raise ValueError(f"Cannot get {item} from {obj}")

            if isinstance(key_item, tuple(CONVERT_TYPE.keys())):
                key_list.append(str(key_item))
            else:
                raise ValueError("Keys need to be datatype object")
        if isinstance(obj, dict) and obj.get("@type") is not None:
            prefix = obj.get("@type") + "_"
        elif hasattr(obj.__class__, "_base"):
            prefix = obj.__class__._base + "_"
        elif hasattr(obj.__class__, "__name__"):
            prefix = obj.__class__.__name__ + "_"
        else:
            raise ValueError(f"Cannot determin prefix from {obj}")
        return prefix + sha256((quote("_".join(key_list))).encode("utf-8")).hexdigest()


class LexicalKey(metaclass=TerminusKey):
    """Generating ID with urllib.parse.quote using provided keys"""

    at_type = "Lexical"

    def __init__(self, keys: Union[str, list]):
        self._keys = keys

    def idgen(self, obj: Union["DocumentTemplate", dict]):
        key_list = []
        for item in self._keys:
            if hasattr(obj, item):
                key_item = ast.literal_eval(f"obj.{item}")
            elif isinstance(obj, dict) and obj.get(item) is not None:
                key_item = obj.get(item)
            else:
                raise ValueError(f"Cannot get {item} from {obj}")

            if isinstance(key_item, tuple(CONVERT_TYPE.keys())):
                key_list.append(str(key_item))
            else:
                raise ValueError("Keys need to be datatype object")
        if isinstance(obj, dict) and obj.get("@type") is not None:
            prefix = obj.get("@type") + "_"
        elif hasattr(obj.__class__, "_base"):
            prefix = obj.__class__._base + "_"
        elif hasattr(obj.__class__, "__name__"):
            prefix = obj.__class__.__name__ + "_"
        else:
            raise ValueError(f"Cannot determin prefix from {obj}")
        return prefix + quote("_".join(key_list))


class ValueHashKey(metaclass=TerminusKey):
    """Generating ID with SHA256"""

    at_type = "ValueHash"

    # def idgen(self, obj: "DocumentTemplate"):
    #     if hasattr(obj.__class__, "_base"):
    #         prefix = obj.__class__._base
    #     else:
    #         prefix = obj.__class__.__name__ + "_"
    #     return prefix + sha256((quote(str(obj))).encode("utf-8")).hexdigest()


class RandomKey(metaclass=TerminusKey):
    """Generating ID with UUID4"""

    at_type = "Random"

    def idgen(self, obj: Union["DocumentTemplate", dict]):
        if isinstance(obj, dict) and obj.get("@type") is not None:
            prefix = obj.get("@type") + "_"
        elif hasattr(obj.__class__, "_base"):
            prefix = obj.__class__._base + "_"
        elif hasattr(obj.__class__, "__name__"):
            prefix = obj.__class__.__name__ + "_"
        else:
            raise ValueError(f"Cannot determin prefix from {obj}")
        return prefix + uuid4().hex


class TerminusClass(type):
    def __init__(cls, name, bases, nmspc):

        if "__annotations__" in nmspc:
            cls._annotations = copy(nmspc["__annotations__"])
        else:
            cls._annotations = {}

        for parent in bases:
            base_annotations = (
                parent._annotations if hasattr(parent, "_annotations") else {}
            )
            cls._annotations.update(base_annotations)

        abstract = False
        if hasattr(cls, "_abstract"):
            if isinstance(cls._abstract, bool):
                abstract = cls._abstract
            else:
                abstract = True

        def init(obj, *args, **kwargs):
            if abstract:
                raise TypeError(f"{name} is an abstract class.")
            for key in cls._annotations:
                if key in kwargs:
                    value = kwargs[key]
                else:
                    value = None
                setattr(obj, key, value)
            obj._annotations = cls._annotations

        cls.__init__ = init

        if cls._schema is not None:
            if not hasattr(cls._schema, "object"):
                cls._schema.object = set()
            cls._schema.add_obj(cls)

        # super().__init__(name, bases, nmspc)

    def __repr__(cls):
        return cls.__name__


class DocumentTemplate(metaclass=TerminusClass):
    _schema = None
    _key = RandomKey()  # default key

    def __init__(self):
        self._new = True

    def __setattr__(self, name, value):
        if name[0] != "_" and value is not None:
            correct_type = self._annotations.get(name)
            check_type(str(value), value, correct_type)
            # import pdb; pdb.set_trace()
            # if not correct_type or not check_type(str(value), value, correct_type):
            #     raise AttributeError(f"{value} is not type {correct_type}")
        super().__setattr__(name, value)

    @classmethod
    def _to_dict(cls):
        result = {"@type": "Class", "@id": cls.__name__}
        if cls.__base__.__name__ != "DocumentTemplate":
            # result["@inherits"] = cls.__base__.__name__
            parents = list(map(lambda x: x.__name__, cls.__mro__))
            result["@inherits"] = parents[1 : parents.index("DocumentTemplate")]
        elif cls.__base__.__name__ == "TaggedUnion":
            result["@type"] = "TaggedUnion"

        if cls.__doc__:
            doc_obj = ClassDoc(cls)
            result["@documentation"] = {
                "@comment": "\n".join(doc_obj["Summary"] + doc_obj["Extended Summary"]),
                "@properties": {
                    thing.name: "\n".join(thing.desc) for thing in doc_obj["Attributes"]
                },
            }

        if hasattr(cls, "_base"):
            result["@base"] = cls._base
        if hasattr(cls, "_subdocument"):
            result["@subdocument"] = cls._subdocument
            result["@key"] = {"@type": "Random"}
        if hasattr(cls, "_abstract"):
            result["@abstract"] = cls._abstract
        if hasattr(cls, "_key") and not hasattr(cls, "_subdocument"):
            if hasattr(cls._key, "_keys"):
                result["@key"] = {
                    "@type": cls._key.__class__.at_type,
                    "@fields": cls._key._keys,
                }
            else:
                result["@key"] = {"@type": cls._key.__class__.at_type}
        if hasattr(cls, "_annotations"):
            for attr, attr_type in cls._annotations.items():
                result[attr] = wt.to_woql_type(attr_type)
        return result

    def _obj_to_dict(self):
        result = {"@type": str(self.__class__)}
        if hasattr(self, "_id"):
            result["@id"] = self._id
        for item in self._annotations.keys():
            if hasattr(self, item):
                the_item = eval(f"self.{item}")  # noqa: S307
                if the_item is not None:
                    if hasattr(the_item.__class__, "_subdocument") or (
                        hasattr(the_item.__class__, "_key")
                        and not hasattr(the_item.__class__._key, "idgen")
                    ):
                        result[item] = the_item._obj_to_dict()
                    elif hasattr(the_item, "_id"):
                        result[item] = {"@id": the_item._id, "@type": "@id"}
                    elif isinstance(the_item, list):
                        new_item = []
                        for sub_item in the_item:
                            if hasattr(sub_item, "_obj_to_dict"):
                                new_item.append(sub_item._obj_to_dict())
                            else:
                                new_item.append(sub_item)
                        result[item] = new_item
                    else:
                        if isinstance(the_item, Enum):
                            result[item] = str(the_item)
                        else:
                            result[item] = the_item
        return result


class EnumMetaTemplate(EnumMeta):
    def __new__(
        metacls,
        cls,
        bases,
        classdict,
        *,
        boundary=None,
        _simple=False,
        **kwds,
    ):
        if "_schema" in classdict:
            schema = classdict.pop("_schema")
            classdict._member_names.remove("_schema")
            new_cls = super().__new__(metacls, cls, bases, classdict)
            new_cls._schema = schema
            if not hasattr(schema, "object"):
                schema.object = set()
            schema.object.add(new_cls)
            return new_cls
        return super().__new__(metacls, cls, bases, classdict)


class EnumTemplate(Enum, metaclass=EnumMetaTemplate):
    def __init__(self, value=None):
        if not value:
            self._value_ = str(self.name)
        else:
            self._value_ = value

    def __str__(self):
        return self._value_

    @classmethod
    def _to_dict(cls):
        result = {"@type": "Enum", "@id": cls.__name__, "@value": []}
        for item in cls.__members__:
            if item[0] != "_":
                result["@value"].append(str(eval(f"cls.{item}")))  # noqa: S307
        # if hasattr(self, "__annotations__"):
        #     for attr, attr_type in self.__annotations__.items():
        #         result[attr] = str(attr_type)
        return result


class TaggedUnion(DocumentTemplate):
    pass


class WOQLSchema:
    def __init__(self):
        self.object = set()

    def commit(self, client: WOQLClient, commit_msg: Optional[str] = None):
        if commit_msg is None:
            commit_msg = "Schema object insert/ update by Python client."
        client.update_document(
            self,
            commit_msg=commit_msg,
            graph_type="schema",
        )
        # all_existing_obj = client.get_all_documents(graph_type="schema")
        # all_existing_id = list(map(lambda x: x.get("@id"), all_existing_obj))
        # insert_schema = WOQLSchema()
        # update_schema = WOQLSchema()
        # for obj in self.all_obj():
        #     obj_str = obj.__name__
        #     if obj_str in all_existing_id:
        #         obj._schema = update_schema
        #         update_schema.add_obj(obj)
        #     else:
        #         obj._schema = insert_schema
        #         insert_schema.add_obj(obj)
        #
        # client.insert_document(
        #     insert_schema,
        #     commit_msg="Schema object insert by Python client.",
        #     graph_type="schema",
        # )
        # client.replace_document(
        #     update_schema,
        #     commit_msg="Schema updated by Python client.",
        #     graph_type="schema",
        # )

    def add_obj(self, obj):
        self.object.add(obj)

    def all_obj(self):
        return self.object

    def to_dict(self):
        return list(map(lambda cls: cls._to_dict(), self.object))

    def copy(self):
        return deepcopy(self)