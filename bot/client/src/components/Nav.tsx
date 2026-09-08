import { NavLink } from 'react-router-dom';

const linkClass = ({ isActive }: { isActive: boolean }) =>
  `px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
    isActive ? 'bg-foreground text-background' : 'text-muted-foreground hover:text-foreground'
  }`;

export const Nav = () => (
  <nav className="flex items-center gap-2 px-6 py-4 shrink-0">
    <NavLink to="/" end className={linkClass}>
      Voice
    </NavLink>
    <NavLink to="/schedule" className={linkClass}>
      Schedule
    </NavLink>
  </nav>
);
