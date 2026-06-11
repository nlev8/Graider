// Shared name-matching helpers for the Analytics tab.
// Moved verbatim from AnalyticsTab.jsx (CQ wave 1 split, behavior-preserving).

var stripNamePunctuation = function(s) { return s.replace(/['\u2018\u2019\-]/g, ''); };

export const studentNameMatchesPeriod = (studentName, students) => {
  if (!students || students.length === 0) return true;
  const nameWords = stripNamePunctuation((studentName || "").toLowerCase()).replace(/[,;.]/g, " ").split(/\s+/).filter(Boolean);
  return students.some((student) => {
    const first = stripNamePunctuation((student.first || "").toLowerCase().trim());
    const last = stripNamePunctuation((student.last || "").toLowerCase().trim());
    if (!first && !last) return false;
    const searchWords = [first, last].join(" ").split(/\s+/).filter(Boolean);
    return searchWords.every((sw) =>
      nameWords.some((nw) => nw.startsWith(sw) || sw.startsWith(nw))
    );
  });
};
