import React, { useState, useEffect, useRef } from "react";

// Defers heavy children (charts) to after first paint using a non-blocking transition.
// Shows a height-matched placeholder instantly so layout doesn't shift.
function DeferredMount({ children, height }) {
  const [show, setShow] = useState(false);
  const ref = useRef(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const obs = new IntersectionObserver(([entry]) => {
      if (entry.isIntersecting) {
        obs.disconnect();
        React.startTransition(() => setShow(true));
      }
    }, { rootMargin: "200px" });
    obs.observe(el);
    return () => obs.disconnect();
  }, []);
  if (!show) return <div ref={ref} style={{ height }} />;
  return children;
}

export default DeferredMount;
