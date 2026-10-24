/** Original vector illustration: no external assets, tracking or image dependency. */
export function LetterFlight() {
  return (
    <svg className="letter-flight" viewBox="0 0 460 380" fill="none" aria-hidden="true">
      <defs>
        <linearGradient id="mail-body" x1="150" y1="100" x2="340" y2="280" gradientUnits="userSpaceOnUse"><stop stopColor="#fff"/><stop offset="1" stopColor="#e5ddff"/></linearGradient>
        <linearGradient id="mail-flap" x1="150" y1="130" x2="290" y2="220" gradientUnits="userSpaceOnUse"><stop stopColor="#fff"/><stop offset="1" stopColor="#f2eefe"/></linearGradient>
        <linearGradient id="heart-clay" x1="210" y1="80" x2="260" y2="165" gradientUnits="userSpaceOnUse"><stop stopColor="#ffacae"/><stop offset="1" stopColor="#f36479"/></linearGradient>
        <linearGradient id="bubble-clay" x1="90" y1="180" x2="180" y2="290" gradientUnits="userSpaceOnUse"><stop stopColor="#bba6ff"/><stop offset="1" stopColor="#8e6ce2"/></linearGradient>
        <filter id="mail-shadow" x="-50%" y="-50%" width="200%" height="220%"><feDropShadow dx="0" dy="15" stdDeviation="10" floodColor="#8a4b33" floodOpacity=".16"/></filter>
      </defs>
      <ellipse cx="237" cy="327" rx="111" ry="15" fill="#dca334" opacity=".3"/>
      <path d="M68 245c-40-16-25-57 8-53-2-32 50-45 61-13 27-4 39 35 10 47" fill="#fff8ee"/>
      <path d="M333 120c-19 0-25-26-5-33 0-25 35-33 42-8 27-5 36 31 11 38" fill="#fff8ee"/>
      <g className="mail-float" filter="url(#mail-shadow)">
        <g transform="rotate(-12 239 215)">
          <rect x="130" y="128" width="218" height="160" rx="28" fill="url(#mail-body)"/>
          <path d="m142 272 83-74c9-8 20-8 29 0l82 74" stroke="#c5b5ef" strokeWidth="3"/>
          <path d="m131 151 89 68c11 9 24 9 36 0l90-68c-3-14-12-23-25-23H157c-13 0-23 9-26 23Z" fill="url(#mail-flap)"/>
          <path d="m143 144 86 65c6 5 13 5 20 0l85-65" stroke="white" strokeWidth="5" strokeLinecap="round"/>
        </g>
        <path d="M234 153s-48-24-48-54c0-25 33-33 48-12 16-21 48-13 48 12 0 30-48 54-48 54Z" fill="url(#heart-clay)"/>
        <path d="M204 98c2-6 8-8 12-6" stroke="#ffd0d3" strokeWidth="6" strokeLinecap="round"/>
        <rect x="84" y="225" width="112" height="77" rx="27" fill="url(#bubble-clay)" transform="rotate(8 140 264)"/>
        <path d="m112 294 2 24 27-17" fill="#9c80ea"/>
        <circle cx="121" cy="260" r="4" fill="#34254e"/><circle cx="161" cy="265" r="4" fill="#34254e"/>
        <path d="M134 276c5 6 12 7 18 2" stroke="#34254e" strokeWidth="4" strokeLinecap="round"/>
      </g>
      <path d="m349 224 8 16 17 3-13 12 2 18-15-9-16 7 4-17-11-14 18-1 6-15Z" fill="#ff8d9c"/>
      <path d="m113 107 5 12 13 2-10 9 2 13-11-6-12 6 3-13-9-10 13-1 6-12Z" fill="#fff"/>
      <circle cx="318" cy="307" r="6" fill="#fff"/><circle cx="72" cy="145" r="5" fill="#a58aef"/>
      <path d="m373 180 12-5m-17-9 4-12M91 315l-12 7" stroke="#684da1" strokeWidth="3" strokeLinecap="round"/>
    </svg>
  );
}
