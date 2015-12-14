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
import dnf
import json
import urllib.request
import ssl
from scipy import spatial
import xml.etree.ElementTree as ET
from collections import Counter

# ---------------------------------------------------------------------------- #

XML_PATH = "data/applications.xml"

# ---------------------------------------------------------------------------- #


class Application(object):
    """ Simple class holding application data """

    def __init__(self, **kwargs):
        self.name = kwargs.get("name")
        self.summary = kwargs.get("summary")
        self.desc = kwargs.get("desc")
        self.category = kwargs.get("category")
        self.tags = kwargs.get("tags")
        self.words = kwargs.get("words")
        self.rating = kwargs.get("rating")
        self.installed = kwargs.get("installed")
        self.recommended = kwargs.get("recommended")
        self.recommended_debug = kwargs.get("recommended_debug", None)


class XmlBuilder(object):
    """ Class building XML with information for available packages """

    def __init__(self):

        # dnf initialization
        self.base = dnf.Base()
        self.base.read_all_repos()
        self.base.fill_sack()

        self._ignored_words = None

        self.xml_root = ET.Element("root")
        self._read_applications()

    @property
    def ignored_words(self):
        """ Ignored words for term frequency analysis """

        if self._ignored_words is None:
            self._ignored_words = []

            with open("data/ignored_words.txt", "r") as f:
                for line in f:
                    if line.startswith("#"):
                        continue
                    self._ignored_words.append(line.strip())

        return self._ignored_words

    def _add_to_tree(self, pkg):
        """ Add package to XML """

        print(pkg.name)

        app = ET.SubElement(self.xml_root, "application")

        name = ET.SubElement(app, "name")
        name.text = pkg.name
        summary = ET.SubElement(app, "summary")
        summary.text = pkg.summary
        desc = ET.SubElement(app, "desc")
        desc.text = pkg.description
        category = ET.SubElement(app, "category")
        category.text = self._get_category(pkg)

        tags = ET.SubElement(app, "tags")
        for t in self._get_tags(pkg):
            tag = ET.SubElement(tags, "tag")
            tag.set("tag", t[0])
            tag.set("value", t[1])

        words = ET.SubElement(app, "words")
        for w in self._get_words(pkg):
            word = ET.SubElement(words, "word")
            word.set("word", w[0])
            word.set("value", str(w[1]))

    def _save_xml(self):
        """ Export the XML file """

        with open(XML_PATH, "wb") as xml:
            xml.write(ET.tostring(self.xml_root))

    def _read_applications(self):
        """ Update the list of available applications """

        query = self.base.sack.query()
        packages = query.available()

        _names = []

        for pkg in packages:
            #if not pkg.name.startswith(("0", "a")):
            #    continue # XXX -- for testing only to avoid waiting for data
            if pkg.name in _names:
                continue
            if self._is_app(pkg):
                self._add_to_tree(pkg)
                _names.append(pkg.name)

        self._save_xml()

    def _is_app(self, package):
        for fname in package.files:
            if fname.endswith(".desktop"):
                return True

        return False

    def _get_tags(self, pkg):
        """ Get package tags from Fedora Tagger application """

        url = "https://apps.fedoraproject.org/tagger/api/v1/%s/" % pkg.name

        try:
            response = urllib.request.urlopen(url)
        except urllib.error.HTTPError:
            return []
        else:
            data = response.read().decode("utf-8")
            parsed_data = json.loads(data)

            tags = parsed_data["tags"]
            parsed_tags = []

            for tag in tags:
                parsed_tags.append((tag["tag"], str(tag["total"])))

        return parsed_tags

    def _get_category(self, pkg):
        """ Get package category from Fedora SCM database """

        # try to get spec file from SCM
        url = "https://pkgs.fedoraproject.org/cgit/%s.git/plain/%s.spec" % (pkg.name, pkg.name)
        # pkgs.fedoraproject.org has an invalid certificate
        context = ssl._create_unverified_context()
        try:
            response = urllib.request.urlopen(url, context=context)
        except urllib.error.HTTPError:
            return "Other"
        else:
            for line in response:
                if line.startswith(b"Group:"):
                    group = line.split()[-1].decode("utf-8")
                    return group

            return "Other"

    def _get_words(self, pkg):
        """ Term frequency analysis of pkg description """

        word_frequency = Counter()

        for word in pkg.description.lower().split():
            if word.endswith((".", ",", "!", "?", ":", ";")):
                word = word[:-1]
            if word in ("*", "-"):
                continue
            if word not in self.ignored_words:
                if word not in word_frequency.keys():
                    word_frequency[word] = 1
                else:
                    word_frequency[word] += 1

        return word_frequency.most_common(10)


class AppReader(object):
    """ Class reading application information from pre-prepared XML file """

    def __init__(self):

        if not os.path.isfile(XML_PATH):
            XmlBuilder()

        self._applications = []
        self._installed = []
        self._user_profile = None
        self._recommendation = None

        self._read_applications()
        self._get_recommended()

    @property
    def applications(self):
        """ List of available applications """

        if not self._applications:
            self._read_applications()

        return self._applications

    @property
    def installed(self):
        """ List of installed applications """

        if not self._installed:
            self._read_installed()

        return self._installed

    @property
    def user_profile(self):
        """ User profile """

        if not self._user_profile:
            self._user_profile = UserProfile(self.applications)

        return self._user_profile

    @property
    def recommendation(self):
        """ Recommendation """

        if not self._recommendation:
            self._recommendation = AppRecommendation(self.user_profile)

        return self._recommendation

    def _read_applications(self):
        """ Update the list of available applications from the XML """

        tree = ET.parse(XML_PATH)
        root = tree.getroot()

        for app in root:
            name = app[0].text
            summary = app[1].text
            desc = app[2].text
            category = app[3].text
            tags = [(t.get("tag"), int(t.get("value"))) for t in app[4]]
            words = [(w.get("word"), int(w.get("value"))) for w in app[5]]
            rating = 0 # FIXME
            installed = self._get_installed(name)
            recommended = False

            new_app = Application(name=name, summary=summary, desc=desc,
                                  category=category, tags=tags, words=words,
                                  rating=rating, installed=installed,
                                  recommended=recommended)

            self._applications.append(new_app)

        self._applications.sort(key=lambda x: x.name.lower())

    def _read_installed(self):
        """ Update the list of installed applications """

        base = dnf.Base()
        base.read_all_repos()
        base.fill_sack()
        query = base.sack.query()
        packages = query.installed()

        self._installed = [p.name for p in packages]

    def _get_recommended(self):
        for app in self.applications:
            app.recommended = app.name in self.recommendation.recommended

    def _get_installed(self, app_name):
        return app_name in self.installed


class UserProfile(object):

    def __init__(self, applications):
        self.applications = applications

        self._favourite_categories = Counter()
        self._favourite_tags = Counter()
        self._all_tags = {}
        self._tags_by_category = {}

        self._favourite_words = Counter()
        self._all_words = {}
        self._words_by_category = {}

        self._create_profile()

    def _create_profile(self):
        """ Create user profile based on installed applications """

        for app in self.applications:
            if app.installed:
                if app.category not in self._favourite_categories.keys():
                    self._favourite_categories[app.category] = 1
                else:
                    self._favourite_categories[app.category] += 1

            for tag in app.tags:
                # all tags
                if tag[0] not in self._all_tags.keys():
                    if tag[1] < 0:
                        self._all_tags[tag[0]] = 0
                    else:
                        self._all_tags[tag[0]] = tag[1]
                else:
                    if tag[1] > 0:
                        self._all_tags[tag[0]] += tag[1]

                if not app.installed:
                    continue

                # tags for installed applications
                if tag[1] <= 0:
                    continue
                if tag[0] not in self._favourite_tags.keys():
                    self._favourite_tags[tag[0]] = tag[1]
                else:
                    self._favourite_tags[tag[0]] += tag[1]

            for word in app.words:
                # all words
                if word[0] not in self._all_words.keys():
                    self._all_words[word[0]] = word[1]
                else:
                    self._all_words[word[0]] += word[1]

                if not app.installed:
                    continue

                # words for installed applications
                if word[1] <= 0:
                    continue
                if word[0] not in self._favourite_words.keys():
                    self._favourite_words[word[0]] = word[1]
                else:
                    self._favourite_words[word[0]] += word[1]

        for category in self.favourite_categories:
            for app in self.applications:
                if not app.installed:
                    continue
                if app.category == category:
                    if category not in self._tags_by_category:
                        self._tags_by_category[category] = Counter()
                    for tag in app.tags:
                        if tag[0] not in self._tags_by_category[category].keys():
                            self._tags_by_category[category][tag[0]] = tag[1]
                        else:
                            self._tags_by_category[category][tag[0]] += tag[1]
                    if category not in self._words_by_category:
                        self._words_by_category[category] = Counter()
                    for word in app.words:
                        if word[0] not in self._words_by_category[category].keys():
                            self._words_by_category[category][word[0]] = word[1]
                        else:
                            self._words_by_category[category][word[0]] += word[1]

    @property
    def favourite_categories(self):
        """ Most common categories among installed applications """

        return self._favourite_categories

    @property
    def all_tags(self):
        """ Tags counts among all applications """

        return self._all_tags

    @property
    def favourite_tags(self):
        """ Most common tags among installed applications """

        return self._favourite_tags

    def get_tags_for_category(self, category):
        """ Most common tags among installed applications in given category """

        return self._tags_by_category[category].most_common(10)

    @property
    def all_words(self):
        """ Tags counts among all applications """

        return self._all_words

    @property
    def favourite_words(self):
        """ Most common tags among installed applications """

        return self._favourite_words

    def get_words_for_category(self, category):
        """ Most common tags among installed applications in given category """

        return self._words_by_category[category].most_common(10)

    def __str__(self):
        s = "<b>Total applications available:</b> %d\n" % len(self.applications)
        s += "<b>Total applications installed:</b> %d\n" % len([app for app in self.applications if app.installed])

        s += "<b>Favourite tags:</b>\n"

        for tag, num in self.favourite_tags.most_common(20):
            s += "\t• %s (%d)\n" % (tag, num)

        s += "<b>Favourite words:</b>\n"

        for word, num in self.favourite_words.most_common(20):
            s += "\t• %s (%d)\n" % (word, num)

        s += "<b>Favourite categories:</b>\n"

        for cat, fav in self.favourite_categories.most_common(6):
            if cat == "Other":
                continue
            s += "\t• %s (%d)\n" % (cat, fav)
            for tag, num in self.get_tags_for_category(cat):
                s += "\t\t\t• %s (%d)\n" % (tag, num)
            s += "\t\t\t-----------------\n"
            for word, num in self.get_words_for_category(cat):
                s += "\t\t\t• %s (%d)\n" % (word, num)

        return s


class AppRecommendation(object):

    def __init__(self, user_profile):

        self.user_profile = user_profile

        self._recommended = []

    @property
    def recommended(self):
        """ List of recommended applications """

        if not self._recommended:
            self._recommended = self._build_recommended()

        return self._recommended

    def _compare_tags(self, compare_type, tags1, tags2):
        """ Compare two sets of tags/words based on its similarity """

        if compare_type == "tags":
            # normalize tags values
            tags1_normalized = []
            for (tag, value) in tags1:
                if self.user_profile.all_tags[tag] > 0:
                    tf = value / sum([val for _tag, val in tags1])
                    idf = sum(list(self.user_profile.all_tags.values())) / self.user_profile.all_tags[tag]
                    value = tf*idf
                tags1_normalized.append((tag, value))
            tags2_normalized = []
            for (tag, value) in tags2:
                if self.user_profile.all_tags[tag] > 0:
                    tf = value / sum([val for _tag, val in tags2])
                    idf = sum(list(self.user_profile.all_tags.values())) / self.user_profile.all_tags[tag]
                    value = tf*idf
                tags2_normalized.append((tag, value))
        elif compare_type == "words":
            tags1_normalized = []
            for (tag, value) in tags1:
                if self.user_profile.all_words[tag] > 0:
                    tf = value / sum([val for _tag, val in tags1])
                    idf = sum(list(self.user_profile.all_words.values())) / self.user_profile.all_words[tag]
                    value = tf*idf
                tags1_normalized.append((tag, value))
            tags2_normalized = []
            for (tag, value) in tags2:
                if self.user_profile.all_words[tag] > 0:
                    tf = value / sum([val for _tag, val in tags2])
                    idf = sum(list(self.user_profile.all_words.values())) / self.user_profile.all_words[tag]
                    value = tf*idf
                tags2_normalized.append((tag, value))

        # both set of tags needs to have same tags (even with value 0) for cosine
        # similarity comparison
        tags1_tags = [tag for tag, _val in tags1_normalized]
        tags2_tags = [tag for tag, _val in tags2_normalized]

        for (tag, _value) in tags1_normalized:
            if tag not in tags2_tags:
                tags2_normalized.append((tag, 0))

        for (tag, _value) in tags2_normalized:
            if tag not in tags1_tags:
                tags1_normalized.append((tag, 0))

        # sort both sets
        tags1_normalized.sort()
        tags2_normalized.sort()

        # vectors -- only normalized values, not the tags names
        vectorA = [val for _tag, val in tags1_normalized]
        vectorB = [val for _tag, val in tags2_normalized]

        similarity = 1 - spatial.distance.cosine(vectorA, vectorB)

        return similarity

    def _build_recommended(self):
        """ Build list of recommended applications """

        recommended = []

        # per category based recommendation
        for category, _fav in self.user_profile.favourite_categories.most_common(5):
            category_tags = self.user_profile.get_tags_for_category(category)
            category_words = self.user_profile.get_words_for_category(category)

            most_rec = Counter()

            for app in self.user_profile.applications:
                if app.installed:
                    continue
                if app.category == category:
                    rec_factor = self._compare_tags("tags", category_tags, app.tags) + \
                                 self._compare_tags("words", category_words, app.words)
                    if rec_factor >= 0:
                        most_rec[app] = rec_factor

            for app, factor in most_rec.most_common(4):
                recommended.append(app.name)

                # with debug information
                app.recommended_debug = RecDebug(app_name=app.name, app_tags=app.tags,
                                                 app_words=app.words, app_category=app.category,
                                                 category_tags=category_tags,
                                                 similarity=factor)

        return recommended


class RecDebug(object):
    """ Simple class holding debug information about recommendation """

    def __init__(self, **kwargs):
        self.app_name = kwargs.get("app_name")
        self.app_tags = kwargs.get("app_tags")
        self.app_words = kwargs.get("app_words")
        self.app_category = kwargs.get("app_category")
        self.category_tags = kwargs.get("category_tags")
        self.similarity = kwargs.get("similarity")

    def __str__(self):
        s = "<b>Recommendation for %s based on:</b>\n" % self.app_name
        s += "\t• Category tags (%s):\n" % self.app_category
        for tag, num in self.category_tags:
            s += "\t\t\t• %s (%d)\n" % (tag, num)
        s += "\t• Application tags:\n"
        for tag, num in self.app_tags:
            s += "\t\t\t• %s (%d)\n" % (tag, num)
        s += "\t• Application words:\n"
        for word, num in self.app_words:
            s += "\t\t\t• %s (%d)\n" % (word, num)
        s += "\t• Similarity: %s\n" % self.similarity

        return s
