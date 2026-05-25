import React, { useCallback, useEffect, useImperativeHandle, useMemo, useRef, useState } from 'react';
import { Card, Layout, Menu, Space, Table } from 'antd';
import type { CardProps, TablePaginationConfig, TableProps } from 'antd';

export type ActionType = {
  reload: () => void;
};

export type ProColumns<T> = Record<string, any> & {
  dataIndex?: keyof T | string;
  title?: React.ReactNode;
  render?: (dom: React.ReactNode, entity: T, index: number, action?: ActionType) => React.ReactNode;
};

type ProCardProps = CardProps & {
  headerBordered?: boolean;
  subTitle?: React.ReactNode;
  [key: string]: any;
};

export const ProCard: React.FC<ProCardProps> = ({ headerBordered: _headerBordered, subTitle, children, ...props }) => (
  <Card {...props}>{children}</Card>
);

type PageContainerProps = {
  header?: {
    title?: React.ReactNode;
    ghost?: boolean;
  };
  children?: React.ReactNode;
};

export const PageContainer: React.FC<PageContainerProps> = ({ header, children }) => (
  <div style={{ padding: 24 }}>
    {header?.title ? <h1 style={{ margin: '0 0 16px', fontSize: 22 }}>{header.title}</h1> : null}
    {children}
  </div>
);

type ProTableProps<T extends object> = Omit<TableProps<T>, 'columns'> & {
  columns: ProColumns<T>[];
  actionRef?: React.Ref<ActionType>;
  request?: (
    params: Record<string, any>,
    sort: Record<string, any>,
    filter: Record<string, any>,
  ) => Promise<{ data: T[]; success?: boolean; total?: number }>;
  toolBarRender?: () => React.ReactNode[];
  search?: unknown;
  dateFormatter?: string;
  cardBordered?: boolean;
  pagination?: TablePaginationConfig | false;
};

export function ProTable<T extends object>({
  columns,
  actionRef,
  request,
  toolBarRender,
  rowKey,
  pagination,
  ...tableProps
}: ProTableProps<T>) {
  const [data, setData] = useState<T[]>([]);
  const [loading, setLoading] = useState(false);
  const [total, setTotal] = useState(0);
  const requestRef = useRef(request);

  useEffect(() => {
    requestRef.current = request;
  }, [request]);

  const load = useCallback(async () => {
    const currentRequest = requestRef.current;
    if (!currentRequest) return;
    setLoading(true);
    try {
      const result = await currentRequest({}, {}, {});
      setData(result.data || []);
      setTotal(result.total || result.data?.length || 0);
    } finally {
      setLoading(false);
    }
  }, []);

  useImperativeHandle(actionRef, () => ({ reload: load }));

  useEffect(() => {
    void load();
  }, [load]);

  const normalizedColumns = useMemo(
    () => columns.filter((column) => !column.hideInTable) as TableProps<T>['columns'],
    [columns],
  );

  return (
    <Card
      title={toolBarRender ? <Space>{toolBarRender()}</Space> : undefined}
      bodyStyle={{ padding: 0 }}
    >
      <Table<T>
        {...tableProps}
        rowKey={rowKey}
        columns={normalizedColumns}
        dataSource={request ? data : tableProps.dataSource}
        loading={loading || tableProps.loading}
        pagination={pagination === false ? false : { total, ...(pagination || {}) }}
      />
    </Card>
  );
}

type ProLayoutProps = {
  title?: React.ReactNode;
  route?: { routes?: Array<{ path?: string; name?: string; icon?: React.ReactNode }> };
  location?: { pathname?: string };
  menuItemRender?: (item: any, dom: React.ReactNode) => React.ReactNode;
  headerTitleRender?: () => React.ReactNode;
  headerContentRender?: () => React.ReactNode;
  avatarProps?: Record<string, any> & {
    title?: React.ReactNode;
    render?: (props: any, dom: React.ReactNode) => React.ReactNode;
  };
  children?: React.ReactNode;
  [key: string]: any;
};

export const ProLayout: React.FC<ProLayoutProps> = ({
  title,
  route,
  location,
  menuItemRender,
  headerTitleRender,
  headerContentRender,
  avatarProps,
  children,
}) => {
  const menuItems = (route?.routes || []).map((item) => ({
    key: item.path || '/',
    icon: item.icon,
    label: menuItemRender ? menuItemRender(item, item.name) : item.name,
  }));
  const avatar = <span>{avatarProps?.title}</span>;

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Layout.Sider width={224} theme="light">
        <div style={{ height: 56, display: 'flex', alignItems: 'center', padding: '0 20px', fontWeight: 700 }}>
          {headerTitleRender ? headerTitleRender() : title}
        </div>
        <Menu mode="inline" selectedKeys={[location?.pathname || '/']} items={menuItems} />
      </Layout.Sider>
      <Layout>
        <Layout.Header style={{ background: '#fff', display: 'flex', alignItems: 'center', padding: '0 20px' }}>
          <div style={{ flex: 1 }}>{headerContentRender?.()}</div>
          {avatarProps?.render ? avatarProps.render({}, avatar) : avatar}
        </Layout.Header>
        <Layout.Content>{children}</Layout.Content>
      </Layout>
    </Layout>
  );
};
