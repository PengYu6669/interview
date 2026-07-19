export function SectionHeading({
  index,
  title,
  description,
  titleId,
}: {
  index: string;
  title: string;
  description?: string;
  titleId: string;
}) {
  return (
    <div className="section-heading">
      <span className="section-index">{index}</span>
      <div>
        <h2 id={titleId}>{title}</h2>
        {description && <p>{description}</p>}
      </div>
    </div>
  );
}
