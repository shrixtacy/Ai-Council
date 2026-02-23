// components/SkeletonCard.jsx
import Skeleton from 'react-loading-skeleton';
import 'react-loading-skeleton/dist/skeleton.css';

export const SkeletonCard = () => (
  <div className="bg-white rounded-lg shadow p-6">
    <Skeleton height={24} width="60%" className="mb-4" />
    <Skeleton count={3} />
    <div className="flex gap-4 mt-4">
      <Skeleton width={80} />
      <Skeleton width={80} />
      <Skeleton width={80} />
    </div>
  </div>
);

export const SkeletonTable = ({ rows = 5, cols = 4 }) => (
  <div className="bg-white rounded-lg shadow overflow-hidden">
    <div className="p-4 border-b">
      <Skeleton height={20} width="30%" />
    </div>
    <div className="divide-y">
      {[...Array(rows)].map((_, i) => (
        <div key={i} className="p-4 flex gap-4">
          {[...Array(cols)].map((_, j) => (
            <Skeleton key={j} height={16} width={`${Math.floor(100 / cols)}%`} />
          ))}
        </div>
      ))}
    </div>
  </div>
);

export const SkeletonText = ({ lines = 3 }) => (
  <div className="space-y-2">
    {[...Array(lines)].map((_, i) => (
      <Skeleton key={i} height={16} width={i === lines - 1 ? '60%' : '100%'} />
    ))}
  </div>
);

export default SkeletonCard;
