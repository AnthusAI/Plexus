'use client';

import { ResponsiveTimeRange } from '@nivo/calendar'

// make sure parent container have a defined height when using
// responsive component, otherwise height will be 0 and
// no chart will be rendered.
// website examples showcase many properties,
// you'll often use just a few of them.
const MyResponsiveTimeRange = (data: any) => (
    <ResponsiveTimeRange
        data={data.data}
        from="2024-09-01"
        to="2024-10-31"
        emptyColor="#eeeeee"
        colors={[ '#61cdbb', '#97e3d5', '#e8c1a0', '#f47560' ]}
        margin={{ top: 40, right: 40, bottom: 100, left: 40 }}
        dayBorderWidth={2}
        dayBorderColor="#ffffff"
    />
);

export default function NivoCalendar() {

    const calendarData =
    [
        {
        "value": 76,
        "day": "2024-10-01"
        },
        {
        "value": 108,
        "day": "2024-10-02"
        },
        {
        "value": 54,
        "day": "2024-10-03"
        }
    ];

    return <div className="w-full h-[280px]">
        <MyResponsiveTimeRange data={calendarData} />
    </div>
}