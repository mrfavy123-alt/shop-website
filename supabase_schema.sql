-- Run once in the Supabase SQL editor for the project.
create table if not exists public.users (
  id uuid primary key references auth.users(id) on delete cascade,
  name text not null,
  email text not null unique,
  created_at timestamptz not null default now()
);

create table if not exists public.products (
  id bigint primary key,
  name text not null,
  category text not null,
  description text not null,
  size text not null,
  badge text not null default '',
  image_url text not null,
  price_minor integer not null check (price_minor >= 0),
  active boolean not null default true
);

create table if not exists public.cart_items (
  user_id uuid not null references public.users(id) on delete cascade,
  product_id bigint not null references public.products(id),
  quantity integer not null check (quantity > 0),
  updated_at timestamptz not null default now(),
  primary key (user_id, product_id)
);

create table if not exists public.orders (
  id bigint generated always as identity primary key,
  user_id uuid not null references public.users(id),
  customer_email text not null,
  status text not null default 'placed' check (status in ('placed', 'processing', 'shipped', 'delivered', 'cancelled')),
  total_minor bigint not null check (total_minor >= 0),
  shipping_address text not null,
  confirmation_email_status text not null default 'pending' check (confirmation_email_status in ('pending', 'sent', 'failed')),
  created_at timestamptz not null default now()
);

create table if not exists public.order_items (
  id bigint generated always as identity primary key,
  order_id bigint not null references public.orders(id) on delete cascade,
  product_id bigint not null references public.products(id),
  product_name text not null,
  unit_price_minor integer not null check (unit_price_minor >= 0),
  quantity integer not null check (quantity > 0)
);

create table if not exists public.bookings (
  id bigint generated always as identity primary key,
  name text not null,
  email text not null,
  phone text not null,
  occasion text not null,
  event_date date not null,
  guest_count integer not null check (guest_count >= 5),
  small_chops text not null,
  notes text not null default '',
  status text not null default 'requested',
  created_at timestamptz not null default now()
);

create table if not exists public.training_programs (
  id bigint generated always as identity primary key,
  code text not null unique,
  title text not null,
  description text not null,
  duration text not null,
  course_fee_minor bigint not null check (course_fee_minor >= 0),
  materials_fee_minor bigint not null check (materials_fee_minor >= 0),
  materials text not null,
  active boolean not null default true
);

create table if not exists public.training_enrollments (
  id bigint generated always as identity primary key,
  program_id bigint not null references public.training_programs(id),
  name text not null,
  email text not null,
  phone text not null,
  payment_token_hash text not null,
  total_minor bigint not null check (total_minor >= 0),
  installment_count integer not null default 2 check (installment_count = 2),
  status text not null default 'requested',
  created_at timestamptz not null default now()
);

create table if not exists public.training_payments (
  id bigint generated always as identity primary key,
  enrollment_id bigint not null references public.training_enrollments(id) on delete cascade,
  installment_number integer not null check (installment_number in (1,2)),
  amount_minor bigint not null check (amount_minor >= 0),
  payment_reference text unique,
  status text not null default 'due',
  due_note text not null,
  paid_at timestamptz,
  unique (enrollment_id, installment_number)
);

create table if not exists public.contact_messages (
  id bigint generated always as identity primary key,
  name text not null,
  email text not null,
  topic text not null,
  message text not null,
  status text not null default 'new',
  created_at timestamptz not null default now()
);

insert into public.training_programs (code,title,description,duration,course_fee_minor,materials_fee_minor,materials) values
 ('chef','Professional Chef Training','Practical Nigerian and continental cooking, kitchen safety, menu costing and food presentation.','6 weeks',24000000,6500000,'Chef jacket and apron, knife kit, recipe workbook, pantry starter pack'),
 ('nutrition','Nutrition & Dietetics Foundations','Nutrition basics, balanced menu planning, food hygiene and healthy cooking practice.','8 weeks',28000000,4500000,'Nutrition workbook, portion guide, menu-planning cards, measuring kit')
on conflict (code) do update set title=excluded.title,description=excluded.description,duration=excluded.duration,course_fee_minor=excluded.course_fee_minor,materials_fee_minor=excluded.materials_fee_minor,materials=excluded.materials;

create index if not exists cart_items_user_idx on public.cart_items(user_id);
create index if not exists orders_user_created_idx on public.orders(user_id, created_at desc);
create index if not exists order_items_order_idx on public.order_items(order_id);

insert into public.products (id, name, category, description, size, badge, image_url, price_minor) values
(1,'Zamac classic burger','Meals','Juicy grilled beef, crisp lettuce, ripe tomato and our house sauce in a toasted brioche bun.','Beef · lettuce · house sauce','Best seller','https://images.unsplash.com/photo-1568901346375-23c9450c58cd?auto=format&fit=crop&w=900&q=88','1250000'),
(2,'Crispy chicken burger','Chicken','Crunchy buttermilk chicken with fresh slaw and a little heat, served in a soft toasted bun.','Buttermilk · slaw · 1 piece','Customer fave','https://images.unsplash.com/photo-1606755962773-d324e0a13086?auto=format&fit=crop&w=900&q=88','1050000'),
(3,'Smoky party jollof, chicken & dodo','Rice dishes','Nigerian party jollof with deep tomato colour and smoky firewood flavour, served with pepper grilled chicken, sweet fried plantain (dodo), slaw and pepper sauce.','Party jollof · grilled chicken · plantain','Party favourite','https://margaretafrica.com/cdn/shop/articles/jollof-rice_42d1dec8-3d61-43c9-82a3-2ff07735cefb.jpg?v=1749490501&width=1920','1650000'),
(4,'Loaded golden fries','Sides','Golden, crisp fries tossed in our house seasoning with a pot of pepper mayo.','Crispy fries · house seasoning','Made to share','https://images.unsplash.com/photo-1573080496219-bb080dd4f877?auto=format&fit=crop&w=900&q=88','450000'),
(5,'Pepper grilled chicken','Chicken','Tender chicken grilled over high heat, brushed with a lively pepper glaze and finished with fresh lemon.','Half chicken · smoky pepper glaze','A little heat','https://images.unsplash.com/photo-1598103442097-8b74394b95c6?auto=format&fit=crop&w=900&q=88','1250000'),
(6,'Nigerian fried rice & chicken','Rice dishes','Colourful Nigerian fried rice tossed with vegetables and served with juicy grilled chicken and dodo.','Vegetable fried rice · grilled chicken','House special','https://images.unsplash.com/photo-1512058564366-18510be2db19?auto=format&fit=crop&w=900&q=88','1450000'),
(7,'Creamy chicken alfredo','Continental','Silky fettuccine in a creamy parmesan sauce with tender grilled chicken and fresh herbs.','Fettuccine · parmesan · herbs','Continental','https://images.unsplash.com/photo-1473093295043-cdd812d0e601?auto=format&fit=crop&w=900&q=88','1600000'),
(8,'Golden Nigerian meat pie','Pastries','A buttery, flaky pastry filled with gently spiced minced beef, potato and carrot.','Flaky pastry · spiced beef','Baked today','https://snapcalorie-webflow-website.s3.us-east-2.amazonaws.com/media/food_pics_v2/medium/nigerian_meat_pie.jpg','250000'),
(9,'Chilled zobo','Drinks','A refreshing house-brewed hibiscus drink with ginger and a bright citrus finish.','Hibiscus · ginger · 500ml','House made','https://proveg.org/ng/wp-content/uploads/sites/4/2024/04/Zobo-drink-scaled-e1696244205636.jpg','150000'),
(10,'Small chops sampler','Pastries','A generous mix of soft golden puff puff, crisp samosas and flaky spring rolls. A favourite for celebrations.','Puff puff · samosa · spring rolls','Party pick','https://startupspot.com.ng/wp-content/uploads/2022/08/images-2-16.jpeg','850000'),
(11,'Fresh mint lemonade','Drinks','Fresh squeezed lemons, a touch of sweetness and mint, served chilled.','Lemon · mint · 400ml','Made fresh','https://snapcalorie-webflow-website.s3.us-east-2.amazonaws.com/media/food_pics_v2/medium/simple_lemonade.jpg','120000'),
(12,'Small chops party tray','Events / Catering','Party-ready puff puff, samosas, spring rolls and savoury bites for 25 guests. Booking request required.','Assorted bites · serves 25','Catering','https://startupspot.com.ng/wp-content/uploads/2022/08/images-2-16.jpeg','9500000'),
(13,'Peppered goat & fried plantain','Meals','Slow cooked goat tossed in a bold pepper sauce with sweet caramelised plantain and fresh onions.','Pepper sauce · caramelised dodo','Local favourite','https://images.unsplash.com/photo-1544025162-d76694265947?auto=format&fit=crop&w=900&q=88','1750000'),
(14,'Chicken stir-fry noodles','Continental','Wok tossed egg noodles with crisp vegetables, tender chicken and a savoury ginger soy glaze.','Egg noodles · vegetables · chicken','Quick favourite','https://images.unsplash.com/photo-1569718212165-3a8278d5f624?auto=format&fit=crop&w=900&q=88','1550000'),
(15,'Classic puff puff box','Pastries','A dozen beautiful, airy, golden classic puff puff, fried fresh.','12 pieces · freshly fried','Soft & golden','https://9jafoodie.com/wp-content/uploads/2011/04/Nigerian-Puff-Puff-Recipe.jpg','500000'),
(16,'Grilled peppered asun','Meals','Char-grilled goat meat tossed with fiery peppers and onions, Nigerian-style asun.','Smoky goat · peppers · onions','Smoky & spicy','https://gugginfoods.com/cdn/shop/products/ASUN_1ca0b5f5-1994-494b-9c49-668ffc410cac_1024x1024.jpg?v=1660064353','1800000'),
(17,'Grilled peppered snail','Meals','Tender snail grilled and finished in a glossy hot pepper sauce with onions.','Peppered snail · onions','Pepper favourite','https://sisiyemmie.com/storage/2025/04/peppered20snail20sisiyemmie10.jpg','2200000'),
(18,'Egusi soup & swallow','Meals','Rich melon-seed egusi with leafy greens and tender meat, served with your choice of swallow.','Egusi · assorted meat · swallow','Nigerian classic','https://www.thefooddictator.com/wp-content/uploads/2015/11/egusi-soup-23-1-4.jpg','1450000'),
(19,'Beef suya','Meals','Smoky grilled beef coated in aromatic suya spice, served with fresh onions and tomato.','Yaji spice · onions · tomato','Street-food favourite','https://images.177milkstreet.com/production/98d8f16e909ec820c76dccb4f9b9496984705ae3-3201x4809.jpg?auto=format&fit=max&h=1200&q=80&w=900','950000'),
(20,'BBQ whole fish','Meals','Whole fish marinated, flame-grilled and brushed with a bold pepper barbecue glaze.','Whole fish · pepper glaze','Fresh off the grill','https://i0.wp.com/www.afrolems.com/wp-content/uploads/2017/02/Barbecue-fish.jpg?ssl=1','2800000'),
(21,'Goat head isi ewu','Meals','Traditional isi ewu: tender goat head in a rich spiced palm-oil sauce with utazi and onions.','Goat head · utazi · onions','Eastern Nigerian special','https://i0.wp.com/www.ascottulip.com/cidsyree/2025/08/isi-ewu-1.jpg?fit=686%2C386&ssl=1','2500000'),
(22,'Birthday cupcake box','Pastries','A party-ready box of soft cupcakes with swirled frosting. Add a custom cupcake order to your birthday booking.','12 cupcakes · custom colours','Made for parties','https://images.unsplash.com/photo-1578922794704-7bdd46f70ce0?auto=format&fit=crop&w=900&q=88','1800000'),
(23,'Banana puff puff box','Pastries','Golden, airy puff puff folded with ripe banana for a soft, naturally sweet bite.','12 pieces · ripe banana','Naturally sweet','https://9jafoodie.com/wp-content/uploads/2011/04/Nigerian-Puff-Puff-Recipe.jpg','600000'),
(24,'Onion puff puff box','Pastries','A savoury puff puff variation with finely chopped onion folded through the light dough.','12 pieces · savoury','Savoury twist','https://9jafoodie.com/wp-content/uploads/2011/04/Nigerian-Puff-Puff-Recipe.jpg','600000')
on conflict (id) do update set name=excluded.name, category=excluded.category, description=excluded.description, size=excluded.size, badge=excluded.badge, image_url=excluded.image_url, price_minor=excluded.price_minor;

alter table public.users enable row level security;
alter table public.products enable row level security;
alter table public.cart_items enable row level security;
alter table public.orders enable row level security;
alter table public.order_items enable row level security;
alter table public.bookings enable row level security;
alter table public.training_programs enable row level security;
alter table public.training_enrollments enable row level security;
alter table public.training_payments enable row level security;
alter table public.contact_messages enable row level security;

grant usage on schema public to anon, authenticated, service_role;
grant select on public.products to anon, authenticated;
grant select on public.users, public.orders, public.order_items to authenticated;
grant select, insert, update, delete on public.cart_items to authenticated;
grant all on public.users, public.products, public.cart_items, public.orders, public.order_items, public.bookings, public.training_programs, public.training_enrollments, public.training_payments, public.contact_messages to service_role;
grant usage, select on all sequences in schema public to service_role;

drop policy if exists "Active menu is public" on public.products;
drop policy if exists "Customers read own profile" on public.users;
drop policy if exists "Customers manage own cart" on public.cart_items;
drop policy if exists "Customers read own orders" on public.orders;
drop policy if exists "Customers read own order items" on public.order_items;
create policy "Active menu is public" on public.products for select using (active = true);
create policy "Customers read own profile" on public.users for select to authenticated using (id = auth.uid());
create policy "Customers manage own cart" on public.cart_items for all to authenticated using (user_id = auth.uid()) with check (user_id = auth.uid());
create policy "Customers read own orders" on public.orders for select to authenticated using (user_id = auth.uid());
create policy "Customers read own order items" on public.order_items for select to authenticated using (exists (select 1 from public.orders where orders.id = order_items.order_id and orders.user_id = auth.uid()));

create or replace function public.create_order(p_user_id uuid, p_name text, p_email text, p_address text, p_items jsonb)
returns table(id bigint, total_minor bigint)
language plpgsql
security definer
set search_path = public
as $$
declare
  v_item jsonb;
  v_product public.products%rowtype;
  v_qty integer;
  v_total bigint := 0;
  v_order_id bigint;
begin
  if p_items is null or jsonb_typeof(p_items) <> 'array' or jsonb_array_length(p_items) = 0 then
    raise exception 'Basket is empty';
  end if;
  if length(trim(p_address)) = 0 or length(p_address) > 500 then raise exception 'Invalid delivery address'; end if;
  insert into public.users (id, name, email) values (p_user_id, trim(p_name), lower(trim(p_email)))
    on conflict (id) do update set name = excluded.name, email = excluded.email;
  for v_item in select value from jsonb_array_elements(p_items) loop
    v_qty := (v_item->>'qty')::integer;
    if v_qty < 1 or v_qty > 100 then raise exception 'Invalid quantity'; end if;
    select * into v_product from public.products where products.id = (v_item->>'id')::bigint and active = true;
    if not found then raise exception 'Product is unavailable'; end if;
    v_total := v_total + v_product.price_minor::bigint * v_qty;
    insert into public.cart_items (user_id, product_id, quantity) values (p_user_id, v_product.id, v_qty)
      on conflict (user_id, product_id) do update set quantity = excluded.quantity, updated_at = now();
  end loop;
  insert into public.orders (user_id, customer_email, total_minor, shipping_address)
    values (p_user_id, lower(trim(p_email)), v_total, trim(p_address)) returning orders.id into v_order_id;
  for v_item in select value from jsonb_array_elements(p_items) loop
    v_qty := (v_item->>'qty')::integer;
    select * into v_product from public.products where products.id = (v_item->>'id')::bigint and active = true;
    insert into public.order_items (order_id, product_id, product_name, unit_price_minor, quantity)
      values (v_order_id, v_product.id, v_product.name, v_product.price_minor, v_qty);
    delete from public.cart_items where user_id = p_user_id and product_id = v_product.id;
  end loop;
  return query select v_order_id, v_total;
end;
$$;

revoke all on function public.create_order(uuid, text, text, text, jsonb) from public, anon, authenticated;
grant execute on function public.create_order(uuid, text, text, text, jsonb) to service_role;

create or replace function public.create_training_enrollment(p_program_code text, p_name text, p_email text, p_phone text, p_payment_token_hash text)
returns table(enrollment_id bigint, first_payment_minor bigint, balance_minor bigint, total_minor bigint)
language plpgsql
security definer
set search_path = public
as $$
declare
  v_program public.training_programs%rowtype;
  v_enrollment_id bigint;
  v_total bigint;
  v_first bigint;
  v_balance bigint;
begin
  select * into v_program from public.training_programs where code = p_program_code and active = true;
  if not found then raise exception 'Training course is unavailable'; end if;
  v_total := v_program.course_fee_minor + v_program.materials_fee_minor;
  v_first := (v_total + 1) / 2;
  v_balance := v_total - v_first;
  insert into public.training_enrollments (program_id,name,email,phone,payment_token_hash,total_minor,installment_count)
    values (v_program.id,trim(p_name),lower(trim(p_email)),trim(p_phone),p_payment_token_hash,v_total,2)
    returning id into v_enrollment_id;
  insert into public.training_payments (enrollment_id,installment_number,amount_minor,due_note) values
    (v_enrollment_id,1,v_first,'Due after your training place is confirmed'),
    (v_enrollment_id,2,v_balance,'Balance due before the course midpoint');
  return query select v_enrollment_id,v_first,v_balance,v_total;
end;
$$;
revoke all on function public.create_training_enrollment(text,text,text,text,text) from public, anon, authenticated;
grant execute on function public.create_training_enrollment(text,text,text,text,text) to service_role;
