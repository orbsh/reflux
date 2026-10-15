"""GENERATED from spec/components.json — do not edit.

Pure data: the vocabulary both the shell and every SDK validate against. It imports
nothing, so it can be the bottom layer.

Regenerate: python3 tools/gen.py      Verify: python3 tools/gen.py --check
"""

from __future__ import annotations

import json

SPEC_VERSION = '0.1.0'
RESERVED_PREFIX = 'reflux:'
OPS = ['create', 'patch', 'insert', 'remove']
BIND_KEYS = ['source', 'event', 'payload']

COMPONENTS: dict = json.loads(
    """
{
  "badge": {
    "attrs": {
      "tone": {
        "default": "neutral",
        "enum": [
          "neutral",
          "info",
          "success",
          "warning",
          "danger"
        ]
      },
      "value": {
        "type": "string"
      }
    },
    "bind": [
      "source"
    ],
    "children": "none",
    "family": "display",
    "local": [],
    "primary": "value"
  },
  "button": {
    "attrs": {
      "disabled": {
        "default": false,
        "type": "bool"
      },
      "label": {
        "type": "string"
      },
      "size": {
        "default": "md",
        "enum": [
          "sm",
          "md"
        ]
      },
      "variant": {
        "default": "secondary",
        "enum": [
          "primary",
          "secondary",
          "ghost",
          "danger"
        ]
      }
    },
    "bind": [
      "event"
    ],
    "children": "none",
    "family": "nav",
    "local": [],
    "primary": "label"
  },
  "card": {
    "attrs": {
      "title": {
        "default": "",
        "type": "string"
      },
      "tone": {
        "default": "plain",
        "enum": [
          "plain",
          "muted",
          "raised"
        ]
      }
    },
    "bind": [
      "source"
    ],
    "children": "many",
    "family": "container",
    "local": []
  },
  "checkbox": {
    "attrs": {
      "disabled": {
        "default": false,
        "type": "bool"
      },
      "label": {
        "type": "string"
      }
    },
    "bind": [
      "source",
      "event",
      "payload"
    ],
    "children": "none",
    "family": "input",
    "local": [
      "checked"
    ]
  },
  "code": {
    "attrs": {
      "lang": {
        "default": "",
        "type": "string"
      },
      "value": {
        "type": "string"
      }
    },
    "bind": [
      "source"
    ],
    "children": "none",
    "family": "display",
    "local": [],
    "primary": "value"
  },
  "empty": {
    "attrs": {
      "hint": {
        "default": "",
        "type": "string"
      },
      "value": {
        "type": "string"
      }
    },
    "bind": [
      "source"
    ],
    "children": "none",
    "family": "feedback",
    "local": [],
    "primary": "value"
  },
  "field": {
    "attrs": {
      "hint": {
        "default": "",
        "type": "string"
      },
      "label": {
        "type": "string"
      },
      "required": {
        "default": false,
        "type": "bool"
      }
    },
    "bind": [],
    "children": "one",
    "family": "container",
    "local": []
  },
  "form": {
    "attrs": {
      "disabled": {
        "default": false,
        "type": "bool"
      },
      "submit_label": {
        "type": "string"
      }
    },
    "bind": [
      "event",
      "payload"
    ],
    "children": "many",
    "family": "container",
    "local": [
      "fields"
    ]
  },
  "heading": {
    "attrs": {
      "level": {
        "default": 2,
        "max": 3,
        "min": 1,
        "type": "int"
      },
      "value": {
        "type": "string"
      }
    },
    "bind": [
      "source"
    ],
    "children": "none",
    "family": "display",
    "local": [],
    "primary": "value"
  },
  "image": {
    "attrs": {
      "alt": {
        "default": "",
        "type": "string"
      },
      "fit": {
        "default": "contain",
        "enum": [
          "contain",
          "cover"
        ]
      },
      "src": {
        "type": "url"
      }
    },
    "bind": [
      "source"
    ],
    "children": "none",
    "family": "display",
    "local": [],
    "primary": "src"
  },
  "input": {
    "attrs": {
      "clearable": {
        "default": false,
        "type": "bool"
      },
      "disabled": {
        "default": false,
        "type": "bool"
      },
      "kind": {
        "default": "text",
        "enum": [
          "text",
          "password",
          "email",
          "number",
          "search"
        ]
      },
      "placeholder": {
        "default": "",
        "type": "string"
      }
    },
    "bind": [
      "source",
      "event",
      "payload"
    ],
    "children": "none",
    "family": "input",
    "local": [
      "value",
      "focus"
    ]
  },
  "link": {
    "attrs": {
      "external": {
        "default": false,
        "type": "bool"
      },
      "href": {
        "type": "url"
      },
      "label": {
        "default": "",
        "type": "string"
      }
    },
    "bind": [
      "source"
    ],
    "children": "none",
    "family": "nav",
    "local": [],
    "primary": "href"
  },
  "option": {
    "attrs": {
      "disabled": {
        "default": false,
        "type": "bool"
      },
      "label": {
        "default": "",
        "type": "string"
      },
      "value": {
        "type": "string"
      }
    },
    "bind": [],
    "children": "none",
    "family": "input",
    "local": [],
    "primary": "value"
  },
  "progress": {
    "attrs": {
      "indeterminate": {
        "default": false,
        "type": "bool"
      },
      "label": {
        "default": "",
        "type": "string"
      },
      "value": {
        "max": 100,
        "min": 0,
        "type": "int"
      }
    },
    "bind": [
      "source"
    ],
    "children": "none",
    "family": "feedback",
    "local": [],
    "primary": "value"
  },
  "rack": {
    "attrs": {
      "density": {
        "default": "normal",
        "enum": [
          "compact",
          "normal"
        ]
      },
      "empty_text": {
        "default": "",
        "type": "string"
      },
      "follow": {
        "default": "none",
        "enum": [
          "none",
          "end"
        ]
      }
    },
    "bind": [
      "source"
    ],
    "children": "many",
    "family": "container",
    "local": [
      "scroll"
    ]
  },
  "row": {
    "attrs": {
      "align": {
        "default": "center",
        "enum": [
          "start",
          "center",
          "end",
          "baseline"
        ]
      },
      "gap": {
        "default": "md",
        "enum": [
          "none",
          "sm",
          "md",
          "lg"
        ]
      },
      "wrap": {
        "default": "nowrap",
        "enum": [
          "nowrap",
          "wrap"
        ]
      }
    },
    "bind": [
      "source"
    ],
    "children": "many",
    "family": "container",
    "local": []
  },
  "select": {
    "attrs": {
      "disabled": {
        "default": false,
        "type": "bool"
      },
      "placeholder": {
        "default": "",
        "type": "string"
      }
    },
    "bind": [
      "source",
      "event",
      "payload"
    ],
    "children": "many",
    "family": "input",
    "local": [
      "value"
    ]
  },
  "stack": {
    "attrs": {
      "align": {
        "default": "stretch",
        "enum": [
          "start",
          "center",
          "end",
          "stretch"
        ]
      },
      "direction": {
        "default": "column",
        "enum": [
          "column",
          "row"
        ]
      },
      "gap": {
        "default": "md",
        "enum": [
          "none",
          "sm",
          "md",
          "lg"
        ]
      }
    },
    "bind": [
      "source"
    ],
    "children": "many",
    "family": "container",
    "local": []
  },
  "switch": {
    "attrs": {
      "disabled": {
        "default": false,
        "type": "bool"
      },
      "label": {
        "type": "string"
      }
    },
    "bind": [
      "source",
      "event",
      "payload"
    ],
    "children": "none",
    "family": "input",
    "local": [
      "checked"
    ]
  },
  "text": {
    "attrs": {
      "size": {
        "default": "md",
        "enum": [
          "sm",
          "md",
          "lg"
        ]
      },
      "tone": {
        "default": "default",
        "enum": [
          "default",
          "muted",
          "success",
          "warning",
          "danger"
        ]
      },
      "value": {
        "type": "string"
      },
      "wrap": {
        "default": true,
        "type": "bool"
      }
    },
    "bind": [
      "source"
    ],
    "children": "none",
    "family": "display",
    "local": [],
    "primary": "value"
  },
  "textarea": {
    "attrs": {
      "disabled": {
        "default": false,
        "type": "bool"
      },
      "placeholder": {
        "default": "",
        "type": "string"
      },
      "rows": {
        "default": 4,
        "max": 40,
        "min": 1,
        "type": "int"
      }
    },
    "bind": [
      "source",
      "event",
      "payload"
    ],
    "children": "none",
    "family": "input",
    "local": [
      "value",
      "focus"
    ]
  }
}
"""
)
