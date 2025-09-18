# python
import streamlit as st
from dataclasses import dataclass
from datetime import datetime, date, time

st.set_page_config(page_title="Schedule Monitoring Calculator", page_icon="📅")

WEEKDAY_START = time(8, 0)
WEEKDAY_END = time(17, 0)  # 17:00 is after-hours

def is_weekday(d: date) -> bool:
    return d.weekday() < 5

def is_normal_window(d: date, t: time | None) -> bool:
    if not is_weekday(d):
        return False
    if t is None:
        return True
    return WEEKDAY_START <= t < WEEKDAY_END

def base_hours(is_first: bool, is_last: bool) -> float:
    return 4.0 if (is_first or is_last) else 2.0

@dataclass(frozen=True)
class Entry:
    d: date
    t: time | None

class Schedule:
    def __init__(self, start_date: date, end_date: date, monitored_entries: list[tuple[date, time | None]]):
        if end_date < start_date:
            raise ValueError("end_date must be >= start_date")
        self.start_date = start_date
        self.end_date = end_date

        by_day: dict[date, time | None] = {}
        for d, t in monitored_entries:
            if start_date <= d <= end_date and d not in by_day:
                by_day[d] = t
        self.entries = [Entry(d, by_day[d]) for d in sorted(by_day)]

    def dry_time(self) -> int:
        return max((self.end_date - self.start_date).days, 0)

    def _split_hours(self) -> tuple[float, float]:
        if not self.entries:
            return 0.0, 0.0
        first_day = self.entries[0].d
        last_day = self.entries[-1].d
        normal = after = 0.0
        for e in self.entries:
            hrs = base_hours(e.d == first_day, e.d == last_day)
            if is_normal_window(e.d, e.t):
                normal += hrs
            else:
                after += hrs
        return normal, after

    def monitoring_hours(self) -> float:
        return self._split_hours()[0]

    def after_hours(self) -> float:
        return self._split_hours()[1]

    def total_monitoring_hours(self) -> float:
        n, a = self._split_hours()
        return n + a

def parse_date_time(entry_str: str):
    s = entry_str.strip()
    if not s:
        return None, None, "Empty entry"
    parts = s.split()
    try:
        d = datetime.strptime(parts[0], "%m/%d/%Y").date()
    except ValueError:
        return None, None, f"Invalid date '{parts[0]}'. Use MM/DD/YYYY."
    t = None
    if len(parts) == 2:
        try:
            t = datetime.strptime(parts[1], "%H%M").time()
        except ValueError:
            return None, None, f"Invalid time '{parts[1]}'. Use HHMM (24h)."
    elif len(parts) > 2:
        return None, None, f"Bad entry '{s}'. Use 'MM/DD/YYYY [HHMM]'."
    return d, t, None

st.title("Schedule Monitoring Calculator")
st.write("First day = 4h, last day = 4h, middle days = 2h. After-hours are weekends or weekdays before 08:00 or at/after 17:00.")

col1, col2 = st.columns(2)
with col1:
    start = st.date_input("Start date", value=date.today())
with col2:
    end = st.date_input("End date", value=date.today())

entries_text = st.text_area(
    "Monitored dates (comma-separated):",
    placeholder="MM/DD/YYYY [HHMM], e.g.\n09/18/2025 0700, 09/19/2025 1800, 09/20/2025",
    height=120,
)

uploaded = st.file_uploader("Or upload a CSV/TXT with one entry per line (MM/DD/YYYY [HHMM])", type=["csv", "txt"])

def load_entries_from_text(s: str):
    parts = [p.strip() for p in s.split(",") if p.strip()]
    return parts

def load_entries_from_file(file):
    lines = file.read().decode("utf-8").splitlines()
    return [ln.strip() for ln in lines if ln.strip()]

raw_parts = []
if uploaded is not None:
    raw_parts = load_entries_from_file(uploaded)
elif entries_text.strip():
    raw_parts = load_entries_from_text(entries_text)

if st.button("Calculate"):
    if end < start:
        st.error("End date must be the same or after start date.")
    elif not raw_parts:
        st.error("Please provide at least one monitored date.")
    else:
        parsed = []
        errors = []
        for p in raw_parts:
            d, t, err = parse_date_time(p)
            if err:
                errors.append(f"{p}: {err}")
            else:
                parsed.append((d, t))

        if errors:
            st.error("Some entries were invalid:\n" + "\n".join(errors))
        else:
            in_range = [(d, t) for d, t in parsed if start <= d <= end]
            out_range = [(d, t) for d, t in parsed if not (start <= d <= end)]

            if out_range:
                with st.expander("Ignored (out of range)"):
                    for d, t in sorted(out_range):
                        ts = f" {t.strftime('%H:%M')}" if t else ""
                        st.write(f"- {d.strftime('%m/%d/%Y')}{ts}")

            if not in_range:
                st.error("No valid monitored dates within the date range.")
            else:
                sched = Schedule(start, end, in_range)
                normal = sched.monitoring_hours()
                after = sched.after_hours()
                total = sched.total_monitoring_hours()

                st.subheader("Results")
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Dry Time (days)", sched.dry_time())
                c2.metric("Normal (hr)", f"{normal:.1f}")
                c3.metric("After-Hours (hr)", f"{after:.1f}")
                c4.metric("Total (hr)", f"{total:.1f}")

                with st.expander("Counted entries"):
                    for e in sched.entries:
                        ts = e.t.strftime("%H:%M") if e.t else "(no time)"
                        tag = "Normal" if is_normal_window(e.d, e.t) else "After"
                        st.write(f"- {e.d.strftime('%m/%d/%Y')} {ts} — {tag}")