# -*- coding: utf-8 -*-
#
# This copyrighted material is made available to anyone wishing to use,
# modify, copy, or redistribute it subject to the terms and conditions of
# the GNU General Public License v.2, or (at your option) any later version.
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY expressed or implied, including the implied warranties of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
# Public License for more details.  You should have received a copy of the
# GNU General Public License along with this program; if not, write to the
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
# Author(s): Vojtech Trefny <mail@vojtechtrefny.cz>
#
# ---------------------------------------------------------------------------- #

import os

import xml.etree.ElementTree as ET
from collections import Counter
import matplotlib.pyplot as pyplot

# ---------------------------------------------------------------------------- #

XML_PATH = "data/applications.xml"

# ---------------------------------------------------------------------------- #


def analyze_apps():
    """ Analyze tag and term distribution in application data """

    if not os.path.isfile(XML_PATH):
        print("Xml file '%s' with app data not found. Run 'XmlBuilder'" \
              "from 'utils.py' first." % XML_PATH)
        return 1

    tags = Counter()
    words = Counter()

    # read the xml with data
    tree = ET.parse(XML_PATH)
    root = tree.getroot()

    # read tags and words (terms) from the xml
    for app in root:
        for t in app[4]:
            tag_name = t.get("tag")
            tag_value = int(t.get("value"))

            if tag_name not in tags.keys():
                tags[tag_name] = tag_value
            else:
                tags[tag_name] += tag_value

        for w in app[5]:
            word_name = w.get("word")
            word_value = int(w.get("value"))

            # just ignore special characters
            if word_name in ("*", "-"):
                continue

            if word_name not in words.keys():
                words[word_name] = word_value
            else:
                words[word_name] += word_value

    # just most common are interesting for barplots
    tags = tags.most_common(30)
    words = words.most_common(30)

    # plot the histograms
    tag_names = [tag for tag, _val in tags]
    tag_values = [val for _tag, val in tags]

    pyplot.figure(1)
    plot1 = pyplot.bar(range(len(tag_names)), tag_values)
    xticks_pos = [0.65*patch.get_width() + patch.get_xy()[0] for patch in plot1]
    pyplot.xticks(xticks_pos, tag_names, rotation=45, ha="right")
    pyplot.subplots_adjust(bottom=0.2)
    pyplot.savefig("data/tags_graph.png")

    word_names = [word for word, _val in words]
    word_values = [val for _word, val in words]

    pyplot.figure(2)
    plot2 = pyplot.bar(range(len(word_names)), word_values)
    xticks_pos = [0.65*patch.get_width() + patch.get_xy()[0] for patch in plot2]
    pyplot.xticks(xticks_pos, word_names, rotation=45, ha="right")
    pyplot.subplots_adjust(bottom=0.2)
    pyplot.savefig("data/words_graph.png")


if __name__ == "__main__":
    analyze_apps()
